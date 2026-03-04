# Spec 013: Workspace Multi-Tenancy

**Status:** planned
**Phase:** v0.7
**Research deps:** research/architecture.md §5 (Recommended Architecture)
**Depends on:** Spec 001 (core search engine), Spec 011 (M365 connector)
**Blocks:** Spec 014 (admin dashboard), Spec 015 (Slack bot)
**Author:** Juan Martinez
**Created:** 2026-03-04
**Updated:** 2026-03-04

## Problem

CodeSight currently operates as a single-tenant engine with one implicit index root. That model fails for consulting deployments and internal multi-team deployments because data, sync status, and access controls are not isolated by tenant boundary.

CodeSight must introduce a first-class **workspace** abstraction so one process can host multiple isolated indexes with deterministic routing and access control.

## Goals

- CodeSight must support named workspaces with isolated storage, sources, and ACL.
- `codesight sync --workspace <name>` must sync only sources bound to that workspace.
- Query execution must read from exactly one workspace index.
- Workspace configuration must persist in SQLite at `~/.codesight/workspaces.db`.
- ACL checks must run before query execution in all workspace-aware interfaces.
- Existing single-folder usage (`CodeSight("/path")`) must remain fully functional.

## Non-Goals

- Role hierarchy inside a workspace (admin/editor/viewer).
- Cross-workspace federated search.
- Cloud-replicated workspace config.
- Quota enforcement on workspace size or source count.
- Returning full file content from search results.

## Solution

### Canonical Storage Layout

```
~/.codesight/
├── workspaces.db                  # workspace config + ACL + sync runs
└── data/
    ├── <legacy_folder_hash>/      # existing single-folder index
    └── ws_<workspace_id>/         # per-workspace isolated index root
        ├── lance/
        ├── metadata.db
        ├── m365-cache/
        └── local-cache/
```

### Workspace Identity and Naming

- `workspace_id` must be UUIDv4 text.
- Workspace name must be unique case-insensitively.
- Workspace name must match regex: `^[A-Za-z0-9][A-Za-z0-9 _.-]{0,99}$`.
- Workspace name must not include `/` or `\\`.

### WorkspaceManager API

```python
class WorkspaceManager:
    def create(name: str, description: str | None, sources: list[DataSource], allowed_emails: list[str]) -> Workspace
    def list() -> list[Workspace]
    def get(name_or_id: str) -> Workspace
    def update(workspace_id: str, *, name: str | None = None, description: str | None = None) -> Workspace
    def delete(workspace_id: str, *, force: bool = False) -> None
    def add_source(workspace_id: str, source: DataSource) -> DataSource
    def remove_source(workspace_id: str, source_id: str) -> None
    def allow(workspace_id: str, email: str) -> None
    def deny(workspace_id: str, email: str) -> None
    def check_access(workspace_id: str, email: str) -> bool
    def sync(workspace_id: str) -> SyncRunResult
```

### Source Types

| Type | `source_config` required keys | Example |
|------|-------------------------------|---------|
| `drive` | `path` | `{ "path": "/Shared Documents/Sales" }` |
| `mail` | `mailbox` | `{ "mailbox": "sales@acme.com" }` |
| `notes` | `notebook` | `{ "notebook": "Project Alpha Notes" }` |
| `sharepoint` | `site_url` | `{ "site_url": "https://acme.sharepoint.com/sites/Sales" }` |
| `local` | `path` | `{ "path": "/srv/codesight/sales" }` |

### Query Routing Contract

- Workspace-aware interfaces must resolve a workspace first.
- Workspace-aware interfaces must call `check_access()` before `search()` or `ask()`.
- Access denial must abort query execution before any index read.

## Core Specifications

**SPEC-013-001: Schema bootstrap and migration**

| Field | Value |
|-------|-------|
| Description | Initialize and migrate `workspaces.db` schema with transactional DDL |
| Trigger | First workspace operation in process |
| Input | Optional existing DB file |
| Output | Valid schema with `schema_version` row |
| Validation | `PRAGMA integrity_check` must return `ok` before migrations |
| Auth Required | No |

Acceptance Criteria:
- [ ] First workspace operation creates `~/.codesight/workspaces.db` when missing.
- [ ] Migrations run in a single transaction; failure rolls back all schema changes.
- [ ] On corruption, operation fails with `workspaces.db appears corrupted. Run 'codesight workspace repair' or restore from backup.`
- [ ] Successful bootstrap inserts `schema_version.version = 1`.

**SPEC-013-002: Workspace CRUD**

| Field | Value |
|-------|-------|
| Description | Create, list, fetch, update, and delete workspace definitions |
| Trigger | API call or `codesight workspace` CLI command |
| Input | Name, optional description, optional `force` on delete |
| Output | Workspace rows and filesystem directory lifecycle |
| Validation | Name regex + uniqueness enforced at DB and service layers |
| Auth Required | No |

Acceptance Criteria:
- [ ] `codesight workspace create "Sales KB"` inserts `workspaces` row and creates `~/.codesight/data/ws_<id>/`.
- [ ] `codesight workspace list` returns one row per workspace with `name`, `sync_status`, `last_synced_at`.
- [ ] `codesight workspace update <id> --name "New Name"` updates name when unique.
- [ ] `codesight workspace delete <id> --yes` removes workspace directory and cascades related rows.
- [ ] Creating duplicate name fails with `Workspace 'Sales KB' already exists.`

**SPEC-013-003: Source binding and validation**

| Field | Value |
|-------|-------|
| Description | Bind validated data sources to a workspace |
| Trigger | `create` with `--source` or `add-source` |
| Input | `type:config` pair |
| Output | New `data_sources` row |
| Validation | Type enum, required config key, normalized JSON config |
| Auth Required | No |

Acceptance Criteria:
- [ ] `--source drive:/Shared Documents/Sales` stores `source_type='drive'` and JSON config with `path`.
- [ ] `--source local:/srv/docs` rejects non-existent path at bind time with `Local source path '/srv/docs' does not exist.`
- [ ] Unknown type fails with `Unsupported source type 'ftp'. Valid types: drive, mail, notes, sharepoint, local.`
- [ ] Duplicate exact source for same workspace fails with `Source already exists in workspace.`

**SPEC-013-004: Workspace sync orchestration**

| Field | Value |
|-------|-------|
| Description | Sync all bound sources for one workspace and index results |
| Trigger | `codesight sync --workspace <name>` or `codesight workspace sync <name>` |
| Input | Workspace name or ID |
| Output | `sync_runs` record and updated workspace status |
| Validation | Workspace exists; per-workspace lock acquired |
| Auth Required | No |

Acceptance Criteria:
- [ ] Sync creates `sync_runs` row with `status='running'`, then updates to `ok` or `error`.
- [ ] Only configured sources for that workspace are read.
- [ ] M365 sources use Spec 011 incremental sync behavior.
- [ ] Source-level failures do not abort other sources.
- [ ] Sync updates `workspaces.last_synced_at` on successful completion.

**SPEC-013-005: Index isolation**

| Field | Value |
|-------|-------|
| Description | Enforce strict storage and query isolation by workspace |
| Trigger | Any workspace-scoped query |
| Input | Resolved workspace ID |
| Output | Results from one workspace index only |
| Validation | Index path derived from UUID only, not raw user input |
| Auth Required | No |

Acceptance Criteria:
- [ ] Querying workspace A never returns chunks from workspace B.
- [ ] Concurrent syncs for different workspace IDs complete without file collisions.
- [ ] Deleting workspace A does not modify any files in workspace B.
- [ ] `CodeSight(workspace="Sales KB")` resolves to one canonical directory.

**SPEC-013-006: Access control list (ACL)**

| Field | Value |
|-------|-------|
| Description | Allow or deny query access by normalized email |
| Trigger | Query requests through workspace-aware interfaces |
| Input | Workspace ID and caller email |
| Output | Boolean allow/deny; denial raises `WorkspaceAccessDenied` |
| Validation | Email normalized to lowercase; RFC 5322-lite validation |
| Auth Required | Caller identity required |

Acceptance Criteria:
- [ ] `allow()` stores lowercase email and prevents duplicates.
- [ ] `check_access()` is case-insensitive and exact-match only.
- [ ] Empty ACL denies all callers.
- [ ] Denied access raises `WorkspaceAccessDenied` with `You don't have access to workspace '<name>'. Contact your admin.`
- [ ] `deny()` removes email and future checks fail immediately.

**SPEC-013-007: CLI contract**

| Field | Value |
|-------|-------|
| Description | Provide full workspace lifecycle via CLI |
| Trigger | `codesight workspace ...` |
| Input | Subcommand and arguments |
| Output | Human-readable output and deterministic exit codes |
| Validation | Missing args produce usage output |
| Auth Required | No |

CLI commands:

```
codesight workspace create <name> [--description TEXT] [--source TYPE:VALUE ...] [--allow EMAIL ...]
codesight workspace list
codesight workspace show <name-or-id>
codesight workspace update <name-or-id> [--name NEW_NAME] [--description TEXT]
codesight workspace delete <name-or-id> [--yes]
codesight workspace sync <name-or-id>
codesight workspace add-source <name-or-id> --source TYPE:VALUE
codesight workspace remove-source <name-or-id> --source-id <id>
codesight workspace allow <name-or-id> <email>
codesight workspace deny <name-or-id> <email>
codesight workspace repair
```

Acceptance Criteria:
- [ ] Unknown subcommand exits `1` and prints valid subcommands.
- [ ] `delete` without `--yes` prompts for confirmation and aborts on negative response.
- [ ] Command success exits `0`; validation or runtime failures exit `1`.
- [ ] `list` output is stable columns: `id`, `name`, `sync_status`, `last_synced_at`.
- [ ] `repair` runs integrity check and reports `workspaces.db integrity check passed.` or a deterministic failure message.

**SPEC-013-008: Backward compatibility path**

| Field | Value |
|-------|-------|
| Description | Preserve legacy single-folder mode after workspace rollout |
| Trigger | `CodeSight("/path")` or legacy CLI calls without workspace |
| Input | Folder path |
| Output | Existing behavior unchanged |
| Validation | Workspace DB presence must not alter legacy index path resolution |
| Auth Required | No |

Acceptance Criteria:
- [ ] Legacy folder indexing and query behavior remains unchanged.
- [ ] Workspace failures do not block legacy mode startup.
- [ ] `workspaces.db` is never included in indexed content.

## Edge Cases & Failure Modes

**EDGE-013-001: Duplicate workspace name**
- Scenario: Create called with existing name (case-insensitive match).
- Expected behavior: reject before filesystem writes.
- Error message: `Workspace 'Sales KB' already exists.`
- Recovery: choose a unique name or delete existing workspace.

**EDGE-013-002: Invalid workspace name**
- Scenario: Name contains `/` or fails regex.
- Expected behavior: reject request.
- Error message: `Workspace name is invalid. Use 1-100 characters: letters, numbers, space, _, -, .`
- Recovery: submit a valid name.

**EDGE-013-003: Sync lock conflict**
- Scenario: A second sync starts for the same workspace while one is running.
- Expected behavior: second request returns conflict and does not enqueue.
- Error message: `Sync already in progress for workspace 'Sales KB'.`
- Recovery: retry after current sync completes.

**EDGE-013-004: Workspace deleted during active sync**
- Scenario: Delete command during running sync.
- Expected behavior: delete fails unless `--force`; default path preserves consistency.
- Error message: `Workspace 'Sales KB' is syncing. Wait for sync completion or use --force.`
- Recovery: wait and retry, or run forced delete in maintenance window.

**EDGE-013-005: Source unreachable**
- Scenario: M365 source returns 503 or local path disappears during sync.
- Expected behavior: mark source failure, continue other sources, mark run `error` if any source failed.
- Error message: `Source sync failed: drive:/Sales (HTTP 503).`
- Recovery: restore source availability and rerun workspace sync.

**EDGE-013-006: Corrupted workspaces.db**
- Scenario: Integrity check fails on open.
- Expected behavior: refuse all workspace operations.
- Error message: `workspaces.db appears corrupted. Run 'codesight workspace repair' or restore from backup.`
- Recovery: run repair command or restore database backup.

**EDGE-013-007: Invalid ACL email**
- Scenario: `allow` called with malformed email.
- Expected behavior: reject and keep ACL unchanged.
- Error message: `Invalid email address '<value>'.`
- Recovery: submit a valid email format.

**EDGE-013-008: Empty ACL query attempt**
- Scenario: Workspace exists but ACL has zero entries.
- Expected behavior: deny query.
- Error message: `You don't have access to workspace 'Sales KB'. Contact your admin.`
- Recovery: admin adds caller email with `codesight workspace allow`.

## Database Schema

### `workspaces`

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | TEXT | PK | UUIDv4 |
| name | TEXT | NOT NULL, UNIQUE COLLATE NOCASE | Display name |
| description | TEXT | NULL | Optional |
| created_at | TEXT | NOT NULL | ISO 8601 UTC |
| updated_at | TEXT | NOT NULL | ISO 8601 UTC |
| last_synced_at | TEXT | NULL | ISO 8601 UTC |
| sync_status | TEXT | NOT NULL | `never`, `syncing`, `ok`, `error` |

Indexes:
- `idx_workspaces_name_nocase(name COLLATE NOCASE)`

### `data_sources`

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | TEXT | PK | UUIDv4 |
| workspace_id | TEXT | NOT NULL, FK | `workspaces.id` |
| source_type | TEXT | NOT NULL | Enum |
| source_config | TEXT | NOT NULL | Canonical JSON |
| created_at | TEXT | NOT NULL | ISO 8601 UTC |

Indexes:
- `idx_data_sources_workspace(workspace_id)`
- `idx_data_sources_unique(workspace_id, source_type, source_config)` UNIQUE

### `workspace_access`

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | TEXT | PK | UUIDv4 |
| workspace_id | TEXT | NOT NULL, FK | `workspaces.id` |
| email | TEXT | NOT NULL | Lowercase normalized |
| granted_at | TEXT | NOT NULL | ISO 8601 UTC |

Indexes:
- `idx_workspace_access_lookup(workspace_id, email)` UNIQUE

### `sync_runs`

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | TEXT | PK | UUIDv4 |
| workspace_id | TEXT | NOT NULL, FK | `workspaces.id` |
| started_at | TEXT | NOT NULL | ISO 8601 UTC |
| completed_at | TEXT | NULL | ISO 8601 UTC |
| status | TEXT | NOT NULL | `running`, `ok`, `error` |
| files_added | INTEGER | NOT NULL DEFAULT 0 | |
| files_updated | INTEGER | NOT NULL DEFAULT 0 | |
| files_deleted | INTEGER | NOT NULL DEFAULT 0 | |
| error_message | TEXT | NULL | Max 500 chars |

Indexes:
- `idx_sync_runs_workspace_started(workspace_id, started_at DESC)`

### `schema_version`

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| version | INTEGER | NOT NULL | Current schema version |
| applied_at | TEXT | NOT NULL | ISO 8601 UTC |

## Alternatives Considered

### Alternative A: Per-workspace JSON files

Trade-off:
- Pro: Human-editable config and easy manual inspection.
- Con: No transactional updates across workspace + sources + ACL; race conditions during concurrent writes; expensive ACL lookups across files.

Decision: Rejected. SQLite provides atomic updates, indexed lookups, and migration control.

### Alternative B: Store workspace config inside each workspace `metadata.db`

Trade-off:
- Pro: Configuration colocated with index data.
- Con: Global operations (`list`, ACL lookup, sync history dashboard) require scanning every workspace DB.

Decision: Rejected. A central registry in `workspaces.db` enables deterministic global queries.

### Alternative C: One process per workspace

Trade-off:
- Pro: Process-level isolation boundary.
- Con: Higher operational cost, more ports/services, duplicated memory footprint, harder upgrades.

Decision: Rejected. Single-process multi-workspace design meets isolation goals with lower operational overhead.

## Observability

- Log `workspace.create` with workspace ID, source count.
- Log `workspace.sync.start` with workspace ID and source count.
- Log `workspace.sync.complete` with workspace ID, status, duration, file counters.
- Log `workspace.sync.source_error` with workspace ID, source ID, sanitized error.
- Log `workspace.access.denied` with workspace ID and email hash prefix.

## Rollback Plan

- Disable workspace flows and continue legacy single-folder mode.
- `workspaces.db` can be archived or removed without affecting legacy indexes under `~/.codesight/data/<legacy_hash>/`.
- No migration mutates existing legacy index files.

## Acceptance Criteria

- [ ] All `SPEC-013-*` acceptance criteria pass in automated tests.
- [ ] Dashboard (Spec 014) reads `workspaces`, `workspace_access`, and `sync_runs` without schema mismatch.
- [ ] Slack bot (Spec 015) uses `check_access()` and denies unauthorized users consistently.
- [ ] Backward compatibility tests confirm legacy mode remains functional.
- [ ] CI runs with mocked connectors; no live M365 calls required.
