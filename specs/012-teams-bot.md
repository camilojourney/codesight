# Spec 012: Microsoft Teams Bot

**Status:** planned
**Phase:** v0.6
**Research deps:** research/architecture.md §5 (Recommended Architecture)
**Depends on:** Spec 001 (core search), Spec 006 (pluggable LLM), Spec 011 (M365 connector)
**Blocks:** None
**Author:** Juan Martinez
**Created:** 2026-03-04
**Updated:** 2026-03-04

## Problem

CodeSight currently has two interfaces: CLI and Streamlit web chat. Both require the user to install Python, run commands, and open a browser. For consulting clients and Juan's own student use case, the natural interface is **Microsoft Teams** — it's already open all day, everyone knows how to use it, and there's zero setup for end users.

A Teams bot that answers questions from indexed M365 content means:
- Users ask questions in Teams chat, get answers with source citations
- No software installation for end users (IT installs the bot once)
- The bot can be added to any channel or used in 1:1 chat
- Answers include Adaptive Cards with expandable source citations and clickable links back to the original document in OneDrive/SharePoint

## Goals

- Teams bot that accepts natural language questions and returns CodeSight answers
- Adaptive Card responses with answer text, confidence badge, and expandable source citations
- Source citations link back to the original M365 document (OneDrive/SharePoint/Outlook deep links)
- Works in 1:1 chat and channel conversations (@ mention in channels)
- Sideloadable on student/dev tenants without admin approval
- Bot runs as a lightweight Python service (aiohttp or FastAPI)

## Non-Goals

- Proactive notifications (bot pushing updates to users) — not needed for search
- File upload handling (user sends a file to bot for indexing) — use `codesight sync` instead
- Multi-tenant SaaS deployment — single-tenant per deployment for now
- Voice/audio messages — text only
- Bot commands for indexing/admin — admin uses CLI, bot is read-only

## Solution

### Architecture

```
Teams Client (user types question)
       |
       v
Microsoft Bot Framework Service (cloud relay)
       |  HTTPS POST /api/messages
       v
+------+--------+
| Teams Bot      |   <-- NEW: src/codesight/bot/teams.py
| (aiohttp)      |
|                |
| on_message()   |   receive question
|   -> ask()     |   call CodeSight API
|   -> card()    |   format Adaptive Card
|   -> reply()   |   send back to Teams
+------+---------+
       |
       v
CodeSight Python API (existing)
  search() / ask()
       |
       v
Indexed M365 content (from Spec 011)
```

### Bot Framework Setup

1. **Azure Bot registration** — register bot in Azure Portal, get App ID + Secret
2. **Bot endpoint** — Python aiohttp server exposing `POST /api/messages`
3. **Teams app manifest** — JSON manifest + icons, zipped as .zip for sideloading
4. **Sideloading** — upload .zip in Teams → Manage Apps → Upload custom app

### Message Flow

```
1. User: "What did Professor X say about the final project?"
2. Bot Framework relays message to bot endpoint
3. Bot calls: engine.ask(question, top_k=5)
4. Bot formats Answer as Adaptive Card:
   ┌──────────────────────────────────┐
   │ 🟢 High Confidence               │
   │                                   │
   │ Professor X mentioned in the      │
   │ March 1 email that the final      │
   │ project is due April 15...        │
   │                                   │
   │ ▼ Sources (3)                     │
   │   📄 email-march-1.txt (p1-2)    │
   │   📓 Class Notes - Week 8 (p3)   │
   │   📁 Syllabus.pdf (p12)          │
   │                                   │
   │ [Open in OneDrive] [Ask Follow-up]│
   └──────────────────────────────────┘
5. Bot sends card back to Teams
```

### Adaptive Card Schema

```json
{
  "type": "AdaptiveCard",
  "version": "1.5",
  "body": [
    {
      "type": "TextBlock",
      "text": "${confidence_badge} ${confidence_level} Confidence",
      "weight": "Bolder"
    },
    {
      "type": "TextBlock",
      "text": "${answer_text}",
      "wrap": true
    },
    {
      "type": "ActionSet",
      "actions": [
        {
          "type": "Action.ShowCard",
          "title": "Sources (${source_count})",
          "card": {
            "type": "AdaptiveCard",
            "body": [
              {
                "type": "TextBlock",
                "text": "${sources_list}",
                "wrap": true
              }
            ]
          }
        }
      ]
    }
  ],
  "actions": [
    {
      "type": "Action.OpenUrl",
      "title": "Open Source",
      "url": "${source_url}"
    }
  ]
}
```

### Key Parameters

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| `CODESIGHT_BOT_APP_ID` | Azure Bot App ID | From Azure Bot registration |
| `CODESIGHT_BOT_APP_SECRET` | Azure Bot App Secret | From Azure Bot registration |
| `CODESIGHT_BOT_PORT` | `3978` (default) | Bot Framework convention |
| `CODESIGHT_BOT_DATA_PATH` | Path to indexed data | Which folder/M365 cache to search |
| Max answer length | 2000 chars | Teams message limit for Adaptive Cards |
| Typing indicator | Shown while processing | User sees "bot is typing..." during ask() |

### Dependencies

- `botbuilder-core>=4.16` — Microsoft Bot Framework SDK for Python
- `botbuilder-integration-aiohttp>=4.16` — aiohttp integration for Bot Framework
- `aiohttp>=3.9` — async HTTP server
- Depends on: Spec 001 (search/ask), Spec 006 (LLM backend), Spec 011 (M365 indexed content)

## Implementation Notes

### File Structure

```
src/codesight/bot/
├── __init__.py
├── teams.py         ← TeamsBot class (message handler)
├── cards.py         ← Adaptive Card builder functions
└── app.py           ← aiohttp server entry point

teams-app/
├── manifest.json    ← Teams app manifest
├── color.png        ← 192x192 app icon
└── outline.png      ← 32x32 outline icon
```

### SPEC Behaviors

- **SPEC-012-001:** Bot receives Teams messages via Bot Framework and calls `CodeSight.ask()`.
- **SPEC-012-002:** Responses formatted as Adaptive Cards with answer, confidence badge, and expandable sources.
- **SPEC-012-003:** Source citations include deep links to original M365 documents when available.
- **SPEC-012-004:** Bot shows typing indicator while processing the question.
- **SPEC-012-005:** Bot works in 1:1 chat and channel conversations (responds to @mentions in channels).
- **SPEC-012-006:** Teams app manifest is valid and sideloadable without admin consent.
- **SPEC-012-007:** CLI `codesight bot` starts the bot server on configured port.

## Edge Cases & Failure Modes

- **EDGE-012-001:** No index exists when user asks question — bot replies "I haven't indexed any documents yet. Ask your admin to run `codesight sync`."
- **EDGE-012-002:** LLM backend unreachable — bot replies "I'm having trouble connecting to the AI service. Search still works — here are the most relevant documents:" + raw search results.
- **EDGE-012-003:** Question too long (>500 chars) — truncate to 500 chars with note, still process.
- **EDGE-012-004:** Bot receives non-text message (image, file) — reply "I can only answer text questions. Try asking something like: What are the payment terms?"
- **EDGE-012-005:** Concurrent questions from multiple users — each request runs independently (stateless handler).
- **EDGE-012-006:** Answer exceeds 2000 char Teams limit — truncate with "..." and add "Ask a more specific question for a detailed answer."
- **EDGE-012-007:** Bot token validation fails (wrong App ID/Secret) — log error, return 401 to Bot Framework.
- **EDGE-012-008:** Channel message without @mention — bot ignores (only responds to @mentions in channels).

## Alternatives Considered

### Alternative A: Outgoing Webhook (no bot registration)

Trade-off: Simpler setup — just a webhook URL, no Azure Bot registration needed.
Rejected because: Outgoing webhooks can't send Adaptive Cards (text-only responses), can't show typing indicators, and are being deprecated in favor of Bot Framework.

### Alternative B: Power Automate / Power Virtual Agents

Trade-off: No-code bot builder, Microsoft-native.
Rejected because: Can't call custom Python code (our search/ask pipeline). Would need a REST API wrapper first (Spec 008), adding unnecessary complexity.

### Alternative C: Slack Bot instead of Teams

Trade-off: Simpler API, better developer experience.
Rejected because: The target client uses M365/Teams. Slack bot can be added later as a separate connector, but Teams is the priority.

## Observability

- Log: `bot.message.received` with user ID (hashed), channel type (1:1 vs channel), question length
- Log: `bot.message.answered` with confidence level, source count, latency
- Log: `bot.message.error` with error type and fallback action taken
- Metric: questions per hour, average response latency, confidence distribution

## Acceptance Criteria

- [ ] Bot server starts with `codesight bot` and listens on configured port
- [ ] Bot responds to Teams 1:1 messages with Adaptive Card answers
- [ ] Bot responds to @mentions in channel conversations
- [ ] Adaptive Card shows confidence badge (high/medium/low/refused)
- [ ] Sources section is expandable and shows file path + page range
- [ ] Source links open the original document when available
- [ ] Typing indicator shown while processing
- [ ] Non-text messages get a helpful error response
- [ ] No-index state returns a clear setup instruction
- [ ] LLM failure falls back to raw search results
- [ ] Teams app manifest validates and sideloads on student tenant
- [ ] Tests pass with mocked Bot Framework (no real Teams calls in CI)
