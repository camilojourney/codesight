# Spec 014: Admin Dashboard

**Status:** planned
**Phase:** v0.7
**Research deps:** research/architecture.md §5 (Recommended Architecture)
**Depends on:** Spec 013 (workspace multi-tenancy), Spec 011 (M365 connector source browsing), Spec 008 (FastAPI runtime patterns)
**Blocks:** None
**Author:** Juan Martinez
**Created:** 2026-03-04
**Updated:** 2026-03-04

## Problem

Workspace functionality is not operationally usable for non-CLI administrators without a control plane. Admins need deterministic workspace management, sync visibility, source selection, and analytics from a browser.

The dashboard must provide full admin lifecycle management while remaining aligned with Spec 013 contracts.

## Goals

- Serve an authenticated admin UI over FastAPI on configurable host and port.
- Manage workspace CRUD, sources, ACL, and manual sync actions through `WorkspaceManager`.
- Display live sync state from `workspaces.sync_status` and sync history from `sync_runs`.
- Provide M365 source browser for `drive`, `mail`, `notes`, and `sharepoint` source binding.
- Provide query analytics using `query_log.db`.
- Run without a frontend build step (Jinja2 + HTMX).

## Non-Goals

- Public anonymous access.
- Real-time WebSocket progress streaming.
- End-user search UI in dashboard.
- Multi-admin role hierarchy.
- Mobile-first layout.

## Solution

### Runtime Topology

```
Admin Browser
    |
    v
FastAPI Dashboard (src/codesight/dashboard)
  - Auth middleware
  - Workspace routes
  - Sync routes
  - Source browser routes
  - Analytics routes
    |
    +--> WorkspaceManager (Spec 013)
    +--> GraphConnector browse APIs (Spec 011)
    +--> query_log.db (analytics read)
```

### Authentication Model

- Required env var: `CODESIGHT_DASHBOARD_API_KEY`.
- Login route: `POST /login` with form field `api_key`.
- Success sets `codesight_admin_token` cookie.
- All routes except `/login` and `/api/health` require valid cookie.
- Unauthorized route access returns `302` redirect to `/login?next=<encoded_path>`.

### Route Inventory

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/health` | Health check JSON |
| GET | `/login` | Login page |
| POST | `/login` | Authenticate admin |
| POST | `/logout` | Clear auth cookie |
| GET | `/` | Workspace list |
| GET | `/workspaces/new` | New workspace form |
| POST | `/workspaces` | Create workspace |
| GET | `/workspaces/{id}` | Workspace detail/edit |
| POST | `/workspaces/{id}` | Update workspace metadata |
| POST | `/workspaces/{id}/delete` | Delete workspace |
| POST | `/workspaces/{id}/sync` | Trigger sync |
| GET | `/workspaces/{id}/sync-status` | HTMX sync status fragment |
| GET | `/workspaces/{id}/sources/browse` | HTMX M365 source browser fragment |
| POST | `/workspaces/{id}/sources` | Add source |
| POST | `/workspaces/{id}/sources/{source_id}/delete` | Remove source |
| POST | `/workspaces/{id}/access` | Add ACL email |
| POST | `/workspaces/{id}/access/{email}/delete` | Remove ACL email |
| GET | `/analytics` | Query analytics page |

## Core Specifications

**SPEC-014-001: Startup and auth enforcement**

| Field | Value |
|-------|-------|
| Description | Start dashboard only with required API key and enforce cookie auth |
| Trigger | `codesight dashboard` or ASGI start |
| Input | `CODESIGHT_DASHBOARD_API_KEY`, optional host/port |
| Output | Running FastAPI app with protected routes |
| Validation | Empty or missing API key fails startup |
| Auth Required | Yes |

Acceptance Criteria:
- [ ] Startup without API key exits with `CODESIGHT_DASHBOARD_API_KEY is required to run the dashboard.`
- [ ] `GET /api/health` returns `200` and `{"status":"ok"}` without auth.
- [ ] `GET /` without cookie returns `302` redirect to `/login`.
- [ ] `POST /login` with correct key sets `codesight_admin_token` and redirects to `/`.
- [ ] `POST /login` with wrong key returns `401` with `Invalid admin API key.`

**SPEC-014-002: Workspace list and status page**

| Field | Value |
|-------|-------|
| Description | Render all workspaces with status and action links |
| Trigger | `GET /` |
| Input | `workspaces` + `sync_runs` aggregates |
| Output | HTML table with metrics |
| Validation | Handles empty dataset |
| Auth Required | Yes |

Acceptance Criteria:
- [ ] One table row renders per workspace.
- [ ] Columns render: `name`, `source_count`, `last_sync`, `item_count`, `sync_status`.
- [ ] `last_sync` displays `Never` when null.
- [ ] Empty state renders `No workspaces yet.` with create action link.
- [ ] `sync_status` badge values match Spec 013 enum exactly.

**SPEC-014-003: Workspace create and edit**

| Field | Value |
|-------|-------|
| Description | Create/update workspace metadata, sources, and ACL from UI |
| Trigger | `GET/POST` workspace form routes |
| Input | Name, description, sources, emails |
| Output | Persisted workspace changes |
| Validation | Uses Spec 013 name/source/email validation |
| Auth Required | Yes |

Acceptance Criteria:
- [ ] Create form includes name, description, source section, and ACL section.
- [ ] Duplicate name error displays inline: `Workspace '<name>' already exists.`
- [ ] Invalid name displays inline: `Workspace name is invalid. Use 1-100 characters: letters, numbers, space, _, -, .`
- [ ] Successful create redirects to `/workspaces/{id}` with success flash.
- [ ] Edit updates metadata without recreating workspace ID.

**SPEC-014-004: Source management and M365 browser**

| Field | Value |
|-------|-------|
| Description | Add/remove sources and browse M365 resources via HTMX |
| Trigger | Source form submit or browse button |
| Input | Source type + config |
| Output | Updated source table fragments |
| Validation | Source type and config validated by Spec 013 rules |
| Auth Required | Yes |

Acceptance Criteria:
- [ ] Source add route rejects invalid type with exact message from Spec 013.
- [ ] `GET /workspaces/{id}/sources/browse?type=drive` returns browsable drive fragment.
- [ ] Missing M365 auth token renders `Not connected to M365. Run 'codesight sync --source m365' to authenticate.`
- [ ] Expired token renders `M365 token expired. Run 'codesight sync --source m365' to re-authenticate.`
- [ ] Browser timeout renders `M365 browser timed out after 10 seconds. Enter source manually.`

**SPEC-014-005: Manual sync trigger and live status**

| Field | Value |
|-------|-------|
| Description | Trigger workspace sync and report progress with HTMX polling |
| Trigger | `POST /workspaces/{id}/sync` |
| Input | Workspace ID |
| Output | Background sync + status fragment updates |
| Validation | Reject when sync already running |
| Auth Required | Yes |

Acceptance Criteria:
- [ ] Trigger returns `202` and sets workspace status to `syncing`.
- [ ] Concurrent trigger returns `409` with `Sync already in progress for workspace '<name>'.`
- [ ] Status fragment polls every 30s only while status is `syncing`.
- [ ] Polling stops automatically on `ok` or `error` state.
- [ ] Latest `sync_runs` record renders files added/updated/deleted counters.

**SPEC-014-006: Sync history viewer**

| Field | Value |
|-------|-------|
| Description | Display last 20 sync runs from `sync_runs` |
| Trigger | `GET /workspaces/{id}` |
| Input | Workspace ID |
| Output | Sync history table |
| Validation | Graceful empty history state |
| Auth Required | Yes |

Acceptance Criteria:
- [ ] Sync history shows newest first, max 20 rows.
- [ ] Columns render: started_at, completed_at, duration_s, status, files_added, files_updated, files_deleted, error_message.
- [ ] Error message displays max 200 chars with ellipsis when truncated.
- [ ] Empty state renders `No syncs run yet.`
- [ ] Data survives process restart because source of truth is `workspaces.db`.

**SPEC-014-007: ACL editor**

| Field | Value |
|-------|-------|
| Description | Add/remove allowed emails for workspace access |
| Trigger | ACL add/remove routes |
| Input | Email address |
| Output | Updated ACL rows |
| Validation | Email format + duplicate checks |
| Auth Required | Yes |

Acceptance Criteria:
- [ ] Valid email add updates ACL table without full page reload.
- [ ] Duplicate email returns inline error: `<email> is already in the access list.`
- [ ] Invalid email returns inline error: `Invalid email address '<value>'.`
- [ ] Remove route deletes ACL entry and updates rendered list.
- [ ] Empty ACL warning renders: `No users have access. This workspace is private.`

**SPEC-014-008: Query analytics page**

| Field | Value |
|-------|-------|
| Description | Render top queries and latency/confidence aggregates |
| Trigger | `GET /analytics` |
| Input | `query_log.db` rows over selected range |
| Output | HTML analytics page |
| Validation | Defaults to last 30 days |
| Auth Required | Yes |

Acceptance Criteria:
- [ ] Top queries table shows top 20 by frequency.
- [ ] P50 and P95 latency values are rendered in milliseconds.
- [ ] Confidence distribution renders high/medium/low/refused percentages.
- [ ] Workspace filter scopes results when selected.
- [ ] Empty analytics state renders `No queries recorded yet.`

## Edge Cases & Failure Modes

**EDGE-014-001: Missing API key at startup**
- Scenario: dashboard process starts without env var.
- Expected behavior: process exits before serving routes.
- Error message: `CODESIGHT_DASHBOARD_API_KEY is required to run the dashboard.`
- Recovery: set env var and restart process.

**EDGE-014-002: Unauthenticated access attempt**
- Scenario: request to protected route without valid cookie.
- Expected behavior: redirect to login and preserve original target.
- Error message: login page banner `Please sign in to continue.`
- Recovery: authenticate on `/login`.

**EDGE-014-003: Invalid login key**
- Scenario: incorrect API key submitted.
- Expected behavior: reject with 401 and no cookie set.
- Error message: `Invalid admin API key.`
- Recovery: submit correct key.

**EDGE-014-004: Concurrent sync trigger**
- Scenario: sync already running and another trigger is submitted.
- Expected behavior: return 409, no second job.
- Error message: `Sync already in progress for workspace '<name>'.`
- Recovery: wait for current sync to complete.

**EDGE-014-005: M365 browse timeout**
- Scenario: Graph browse call exceeds 10s timeout.
- Expected behavior: return HTMX error fragment, no crash.
- Error message: `M365 browser timed out after 10 seconds. Enter source manually.`
- Recovery: retry browse or enter source manually.

**EDGE-014-006: Invalid source add request**
- Scenario: add source with unsupported type.
- Expected behavior: reject and keep existing source list unchanged.
- Error message: `Unsupported source type '<type>'. Valid types: drive, mail, notes, sharepoint, local.`
- Recovery: select a supported source type.

**EDGE-014-007: Workspace deleted by CLI while page open**
- Scenario: admin views workspace detail after external deletion.
- Expected behavior: next action returns 404 and redirects to list.
- Error message: `Workspace not found.`
- Recovery: refresh workspace list and recreate workspace if needed.

**EDGE-014-008: `query_log.db` missing**
- Scenario: analytics page requested before any query logging setup.
- Expected behavior: page renders empty analytics state.
- Error message: `No queries recorded yet.`
- Recovery: none required; data appears after queries are logged.

## Data Contracts

### `query_log.db` table: `query_log`

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | TEXT | PK | UUIDv4 |
| workspace_id | TEXT | NULL | Null for legacy mode |
| query_text | TEXT | NOT NULL | Max 500 chars |
| confidence | TEXT | NOT NULL | `high`, `medium`, `low`, `refused` |
| latency_ms | INTEGER | NOT NULL | End-to-end answer latency |
| source_count | INTEGER | NOT NULL DEFAULT 0 | |
| created_at | TEXT | NOT NULL | ISO 8601 UTC |

Indexes:
- `idx_query_log_created(created_at)`
- `idx_query_log_workspace_created(workspace_id, created_at)`

### Cross-Spec schema alignment

- `sync_runs` is defined in Spec 013 and consumed by this dashboard.
- Dashboard must not define a divergent `sync_runs` schema.
- ACL operations must invoke Spec 013 `allow()` and `deny()`.

## Implementation Notes

### File Structure

```
src/codesight/dashboard/
├── app.py
├── auth.py
├── routes/
│   ├── workspaces.py
│   ├── sources.py
│   └── analytics.py
├── templates/
│   ├── base.html
│   ├── login.html
│   ├── workspaces/list.html
│   ├── workspaces/detail.html
│   ├── workspaces/form.html
│   └── analytics.html
└── query_log.py
```

### Sync execution model

- Sync trigger uses FastAPI `BackgroundTasks`.
- Route writes initial `syncing` state, then background task calls `WorkspaceManager.sync()`.
- Task result updates `sync_runs` and `workspaces.sync_status`.

## Alternatives Considered

### Alternative A: React SPA with JSON API

Trade-off:
- Pro: Rich client-side interactions and component reuse.
- Con: Build tooling, static asset pipeline, frontend dependency maintenance, and larger deployment artifact.

Decision: Rejected. Server-rendered HTMX flow satisfies scope with lower operational complexity.

### Alternative B: Streamlit admin surface

Trade-off:
- Pro: Quick development with existing familiarity.
- Con: Weak fit for granular route auth, HTMX fragment contracts, and deterministic form workflows.

Decision: Rejected. FastAPI + Jinja2 gives precise control over auth and route behavior.

### Alternative C: Django admin

Trade-off:
- Pro: Batteries-included admin features.
- Con: Additional framework stack, ORM migration overlap with existing SQLite logic, and integration overhead.

Decision: Rejected. FastAPI stack already exists and aligns with current runtime.

## Observability

- Log `dashboard.request` with method, route, status, latency.
- Log `dashboard.login.failed` with hashed IP.
- Log `dashboard.sync.triggered` with workspace ID.
- Log `dashboard.sync.conflict` on 409 responses.
- Log `dashboard.sources.browse.timeout` with workspace ID and source type.

## Rollback Plan

- Stop running `codesight dashboard`.
- Keep `workspaces.db` and `query_log.db` intact.
- CLI and bot interfaces continue to function because dashboard is a consumer of existing services.

## Acceptance Criteria

- [ ] All `SPEC-014-*` acceptance criteria pass with route tests.
- [ ] Protected routes consistently return `302` redirect when unauthenticated.
- [ ] All workspace operations call Spec 013 APIs and preserve schema compatibility.
- [ ] No route requires live network access in CI; Graph calls are mocked.
