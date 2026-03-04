# Spec 015: Slack Bot

**Status:** planned
**Phase:** v0.7
**Research deps:** research/architecture.md §5 (Recommended Architecture)
**Depends on:** Spec 001 (core search/ask), Spec 006 (LLM backend), Spec 013 (workspace multi-tenancy + ACL)
**Blocks:** None
**Author:** Juan Martinez
**Created:** 2026-03-04
**Updated:** 2026-03-04

## Problem

Teams support exists (Spec 012), but many deployments run daily collaboration in Slack. CodeSight needs a Slack-native interface with the same answer quality and citation behavior while preserving workspace isolation and access control.

## Goals

- Receive Slack questions from DMs, `app_mention`, and `/codesight` slash command.
- Route every query to one configured CodeSight workspace.
- Enforce Spec 013 ACL before calling `search()` or `ask()`.
- Reply with Block Kit containing confidence label, answer text, and source citations.
- Acknowledge inbound Slack events within 3 seconds.
- Start via `codesight slack-bot` CLI with deterministic startup validation.

## Non-Goals

- File upload indexing from Slack.
- Proactive notifications.
- Multi-workspace routing per channel in v0.7.
- Slack Connect cross-workspace identity federation.
- Voice or audio input.

## Solution

### Runtime Architecture

```
Slack Client
   |
   v
Slack Events API or Socket Mode
   |
   v
CodeSight Slack Bot (Bolt for Python)
  - validate event
  - extract question
  - resolve user email
  - check workspace ACL (Spec 013)
  - call CodeSight.ask()
  - render Block Kit
   |
   v
CodeSight Engine + Workspace Index
```

### Startup Modes

| Mode | Required vars | Listener |
|------|---------------|----------|
| Socket Mode | `CODESIGHT_SLACK_BOT_TOKEN`, `CODESIGHT_SLACK_APP_TOKEN`, `CODESIGHT_SLACK_WORKSPACE` | Bolt socket handler |
| HTTP Events | `CODESIGHT_SLACK_BOT_TOKEN`, `CODESIGHT_SLACK_SIGNING_SECRET`, `CODESIGHT_SLACK_WORKSPACE` | HTTP `/slack/events` + `/slack/commands` |

Mode selection rule:
- If `CODESIGHT_SLACK_APP_TOKEN` is set, bot must run in Socket Mode.
- Otherwise, bot must run HTTP mode and require signing secret.

### Required Slack Scopes

- `app_mentions:read`
- `chat:write`
- `im:history`
- `im:read`
- `commands`
- `users:read`
- `users:read.email`

`users:read.email` is mandatory because ACL checks require caller email.

### Workspace Routing Contract

- `CODESIGHT_SLACK_WORKSPACE` is required.
- Bot must resolve workspace at startup and fail fast if missing.
- Bot must call `WorkspaceManager.check_access(workspace_id, caller_email)` for every query.
- Denied callers receive an access-denied message and query is not executed.

## Core Specifications

**SPEC-015-001: Startup validation and mode selection**

| Field | Value |
|-------|-------|
| Description | Validate env vars, workspace, and runtime mode before bot accepts events |
| Trigger | `codesight slack-bot` |
| Input | Env vars and optional CLI flags |
| Output | Running bot process or startup failure |
| Validation | Required tokens and workspace existence |
| Auth Required | N/A |

Acceptance Criteria:
- [ ] Missing `CODESIGHT_SLACK_BOT_TOKEN` exits with `CODESIGHT_SLACK_BOT_TOKEN is required.`
- [ ] Missing `CODESIGHT_SLACK_WORKSPACE` exits with `CODESIGHT_SLACK_WORKSPACE is required.`
- [ ] Nonexistent workspace exits with `Workspace '<name>' not found. Run 'codesight workspace list' to see available workspaces.`
- [ ] Socket token present selects Socket Mode automatically.
- [ ] HTTP mode without signing secret exits with `CODESIGHT_SLACK_SIGNING_SECRET is required in HTTP mode.`

**SPEC-015-002: Event intake and acknowledgement**

| Field | Value |
|-------|-------|
| Description | Receive Slack events and acknowledge within deadline |
| Trigger | `app_mention`, DM `message`, `/codesight` |
| Input | Slack payload |
| Output | Immediate ack and asynchronous processing |
| Validation | Signature verification in HTTP mode |
| Auth Required | Slack request validation |

Acceptance Criteria:
- [ ] Every supported event is acknowledged in under 3 seconds.
- [ ] Invalid signature request returns `401` and processing stops.
- [ ] Unsupported event types are ignored without error responses.
- [ ] Slash command requests are acknowledged before `ask()` execution.

**SPEC-015-003: Question extraction and normalization**

| Field | Value |
|-------|-------|
| Description | Normalize question text for engine calls |
| Trigger | Any supported question event |
| Input | Raw Slack text |
| Output | Clean question string |
| Validation | Max 500 chars, non-empty after normalization |
| Auth Required | Yes |

Acceptance Criteria:
- [ ] Channel mention strips bot mention prefix before query.
- [ ] Question longer than 500 chars is truncated to 500.
- [ ] Empty question returns `Usage: /codesight <your question>` for slash commands.
- [ ] Empty DM or mention question returns `Please send a text question, for example: What are the payment terms?`

**SPEC-015-004: Workspace ACL enforcement**

| Field | Value |
|-------|-------|
| Description | Enforce access control using caller email and Spec 013 ACL |
| Trigger | Before `search()` or `ask()` |
| Input | Slack user ID -> email lookup |
| Output | Allow executes query; deny returns policy message |
| Validation | Email resolution required |
| Auth Required | Yes |

Acceptance Criteria:
- [ ] Bot resolves caller email via Slack Users API for each request.
- [ ] If email lookup fails due missing scope, response is `Bot is missing Slack scope 'users:read.email'. Contact your admin.`
- [ ] If ACL denies access, response is `You don't have access to workspace '<name>'. Contact your admin.`
- [ ] On deny, bot does not call `engine.ask()` or `engine.search()`.

**SPEC-015-005: Answer formatting with Block Kit**

| Field | Value |
|-------|-------|
| Description | Render answer payload with confidence and source citations |
| Trigger | Successful engine response |
| Input | `Answer(text, confidence, sources)` |
| Output | Block Kit message |
| Validation | Max answer text 3000 chars |
| Auth Required | Yes |

Confidence mapping:
- `high` -> `:large_green_circle: High Confidence`
- `medium` -> `:large_yellow_circle: Medium Confidence`
- `low` -> `:red_circle: Low Confidence`
- `refused` -> `:black_circle: No Answer Found`

Acceptance Criteria:
- [ ] Block payload validates against Slack Block Kit schema.
- [ ] Answer text over 3000 chars is truncated with suffix `... (truncated)`.
- [ ] Up to 5 sources are shown with file label and page/line range.
- [ ] `http`/`https` source URLs render clickable Slack links.
- [ ] Non-HTTP URLs render as plain text labels.

**SPEC-015-006: Channel, DM, and slash command behavior**

| Field | Value |
|-------|-------|
| Description | Deterministic behavior by conversation type |
| Trigger | Event type and channel type |
| Input | Slack event metadata |
| Output | Reply target and visibility |
| Validation | Channel non-mentions ignored |
| Auth Required | Yes |

Acceptance Criteria:
- [ ] DM text message triggers direct DM reply.
- [ ] `app_mention` in channel triggers threaded reply (`thread_ts` equals source message ts).
- [ ] Channel message without mention gets no response.
- [ ] `/codesight` response is ephemeral by default.
- [ ] `/codesight --public <question>` posts in channel thread when option is present.

**SPEC-015-007: Failure fallback behavior**

| Field | Value |
|-------|-------|
| Description | Return explicit user-safe fallbacks on runtime failures |
| Trigger | Engine or Slack API exceptions |
| Input | Exception class and context |
| Output | Fallback response or logged terminal failure |
| Validation | No secret leakage in logs or responses |
| Auth Required | Yes |

Acceptance Criteria:
- [ ] LLM failure falls back to search response with `I'm having trouble connecting to the AI service. Here are the most relevant documents:`
- [ ] Empty index responds with `I haven't indexed any documents yet. Ask your admin to run 'codesight sync --workspace <name>'.`
- [ ] Slack API rate limit retries with exponential backoff for up to 30 seconds.
- [ ] If reply fails after retry budget, error is logged and processing ends without crash.

## Edge Cases & Failure Modes

**EDGE-015-001: Missing required bot token**
- Scenario: bot starts without `CODESIGHT_SLACK_BOT_TOKEN`.
- Expected behavior: startup aborts.
- Error message: `CODESIGHT_SLACK_BOT_TOKEN is required.`
- Recovery: set env var and restart.

**EDGE-015-002: Missing workspace config**
- Scenario: `CODESIGHT_SLACK_WORKSPACE` not set.
- Expected behavior: startup aborts.
- Error message: `CODESIGHT_SLACK_WORKSPACE is required.`
- Recovery: set workspace name and restart.

**EDGE-015-003: Workspace not found**
- Scenario: configured workspace name does not exist.
- Expected behavior: startup aborts.
- Error message: `Workspace '<name>' not found. Run 'codesight workspace list' to see available workspaces.`
- Recovery: correct workspace name or create workspace.

**EDGE-015-004: Missing email scope**
- Scenario: Slack app lacks `users:read.email`.
- Expected behavior: deny query because ACL identity cannot be resolved.
- Error message: `Bot is missing Slack scope 'users:read.email'. Contact your admin.`
- Recovery: add scope, reinstall app, retry.

**EDGE-015-005: ACL denied user**
- Scenario: user email not in workspace ACL.
- Expected behavior: bot returns denial and does not query index.
- Error message: `You don't have access to workspace '<name>'. Contact your admin.`
- Recovery: admin adds user with `codesight workspace allow`.

**EDGE-015-006: Question exceeds limit**
- Scenario: text > 500 chars.
- Expected behavior: truncate and continue.
- Error message: `Note: your question was truncated to 500 characters.`
- Recovery: user sends shorter question for better precision.

**EDGE-015-007: Empty workspace index**
- Scenario: workspace exists but never synced.
- Expected behavior: return setup instruction.
- Error message: `I haven't indexed any documents yet. Ask your admin to run 'codesight sync --workspace <name>'.`
- Recovery: admin runs workspace sync.

**EDGE-015-008: Slack rate limit exceeded**
- Scenario: `chat.postMessage` returns 429.
- Expected behavior: retry with backoff until 30-second budget expires.
- Error message: `Slack is rate limiting responses right now. Please retry in a few seconds.` (sent only if retry budget is exhausted).
- Recovery: automatic retries; operator inspects `slack.rate_limit.hit` logs when repeated.

## Event and Endpoint Contract

### Bolt handlers

```python
app.event("app_mention")
app.event("message")         # filtered to DMs only
app.command("/codesight")
```

### HTTP mode endpoints

| Method | Path | Contract |
|--------|------|----------|
| POST | `/slack/events` | Slack-signed event payload, returns 200 on ack |
| POST | `/slack/commands` | Slack-signed slash command payload, returns 200 on ack |

## Security

- Bot and signing tokens must come from environment variables only.
- Tokens must never be logged.
- HTTP mode must verify Slack signatures on every request.
- Logs must include Slack user ID, not email or display name.
- Logged question text must be truncated to 50 chars.

## Implementation Notes

### File structure

```
src/codesight/bot/
├── slack.py      # Bolt app and handlers
├── blocks.py     # Block Kit builders
└── __init__.py
```

### Processing sequence

1. Ack event.
2. Normalize question.
3. Resolve caller email.
4. Check ACL.
5. Call `engine.ask()`.
6. Render and send response.

## Alternatives Considered

### Alternative A: Slack RTM API

Trade-off:
- Pro: WebSocket model without inbound HTTP setup.
- Con: Legacy surface and lower parity with modern Slack app capabilities.

Decision: Rejected. Bolt Socket Mode provides current supported model with simpler operations.

### Alternative B: Outgoing webhook only

Trade-off:
- Pro: Minimal setup.
- Con: No DM support, no slash command parity, limited formatting behavior.

Decision: Rejected. Events API + Bolt is required for complete interface coverage.

### Alternative C: Disable ACL checks in Slack layer

Trade-off:
- Pro: Simpler implementation with no email lookup.
- Con: Violates Spec 013 access contract and permits unauthorized workspace queries.

Decision: Rejected. ACL enforcement is mandatory.

## Observability

- Log `slack.event.received` with event type and channel type.
- Log `slack.query.allowed` with workspace ID and user ID.
- Log `slack.query.denied` with workspace ID and user ID.
- Log `slack.answer.sent` with confidence and latency.
- Log `slack.error` with normalized error type.

## Rollback Plan

- Stop `codesight slack-bot` process.
- Keep workspace and index data unchanged.
- Teams, CLI, and dashboard interfaces remain unaffected.

## Acceptance Criteria

- [ ] All `SPEC-015-*` acceptance criteria pass with mocked Slack and engine tests.
- [ ] ACL enforcement behavior matches Spec 013 exactly.
- [ ] Startup validation rejects missing tokens, missing workspace, and invalid workspace.
- [ ] CI tests run without real Slack network calls.
