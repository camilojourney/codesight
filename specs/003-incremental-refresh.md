# Spec 003: Incremental Refresh

**Status:** draft
**Phase:** v0.5
**Research deps:** research/architecture.md §4.5 (JIT Context — incremental re-indexing), research/stack.md §3.2 (LanceDB — no native incremental indexing), research/stack.md §3.4 (Migration Path — incremental indexing upgrade)
**Depends on:** Spec 001 (core search engine — chunk storage, LanceDB + SQLite FTS5 pipeline)
**Blocks:** none
**Created:** 2026-02-24
**Updated:** 2026-03-04

## Problem

When a client updates a few documents in their folder, re-indexing reads every file even though most haven't changed. Content hashing at the chunk level prevents re-embedding unchanged chunks, but file reading, parsing, and chunking still happens for all files. For a 5,000-document folder, this wastes minutes on unchanged files.

Clients expect that updating one document and searching again takes seconds, not minutes. Without incremental refresh, the practical re-index frequency is low — clients wait for a full rebuild or get stale results.

## Goals

- Re-index of a 5,000-doc folder with 10 changed files completes in under 10 seconds (vs minutes for full rebuild) (research/architecture.md §4.5) [VERIFIED]
- Git repos: detect changed files using git's native diff mechanism, not file scanning
- Non-git folders: detect changed files using filesystem modification timestamps
- Only changed and new files enter the parse → chunk → embed → store pipeline
- Deleted files are purged from both the vector store and FTS index immediately
- `force_rebuild=True` always triggers a full rebuild, bypassing incremental logic
- `status()` reports the last-indexed commit hash (git) or timestamp (non-git)

## Non-Goals

- Real-time file watching via inotify/FSEvents — a background daemon adds platform-specific complexity; polling or explicit re-index calls are sufficient for consulting deployments
- Git submodule support — submodule detection is deferred
- Tracking files outside the indexed folder — the indexed folder is the only scope
- Webhook-triggered re-index — planned for v0.6 with M365 connectors (delta queries)

## Solution

The indexer checks the stored `last_commit` (for git repos) or `last_indexed_at` timestamp (for non-git folders) against the current state. It builds a minimal change set — added, modified, and deleted files — then processes only that set through the standard pipeline.

```
Re-index entry point:
    |
    ├── Git repo detected?
    |   ├── Yes → compare HEAD to last_commit via git diff → changed file list
    |   └── No  → compare file mtimes to last_indexed_at → changed file list
    |
    ├── Changed file count > 1,000?
    |   └── Yes → full rebuild (cheaper than partial at this scale)
    |
    ├── For each changed/new file:
    |   └── Parse → chunk → embed → store (standard pipeline, identical to full index)
    |
    ├── For each deleted file:
    |   └── Remove all chunks from LanceDB + SQLite FTS5 by file_path
    |
    └── Update repo_meta: last_indexed_at, last_commit (if git)
```

The incremental path is behaviorally identical to a full index for the files it processes. No special handling is needed in the parse/chunk/embed/store stages — only the file selection logic changes.

## Core Specifications

**SPEC-001: Git-based change detection**

| Field | Value |
|-------|-------|
| Description | When the indexed folder is a git repository, determine changed files by diffing the current HEAD against the last indexed commit stored in `repo_meta` |
| Trigger | `index()` called on a git repo that has a `last_commit` recorded in `repo_meta` |
| Input | `last_commit` hash from `repo_meta`, current HEAD commit hash |
| Output | List of file paths: added, modified, deleted since `last_commit` |
| Validation | If `last_commit` is absent or unreachable (e.g., after a force-push reset), fall back to full rebuild |
| Auth Required | No |

Acceptance Criteria:
- [ ] Modifying one file in a 500-doc git repo → re-index processes exactly that file
- [ ] Adding a new file → it is indexed; no other files are re-parsed
- [ ] Deleting a file → its chunks are removed from LanceDB and SQLite FTS5
- [ ] `repo_meta.last_commit` updated to HEAD after each successful incremental run

**SPEC-002: mtime-based change detection**

| Field | Value |
|-------|-------|
| Description | For non-git folders, identify changed files by comparing each file's modification timestamp to `last_indexed_at` stored in `repo_meta` |
| Trigger | `index()` called on a non-git folder that has a `last_indexed_at` timestamp |
| Input | `last_indexed_at` from `repo_meta`, filesystem mtimes of all files in the folder |
| Output | List of file paths whose mtime is strictly after `last_indexed_at`, plus files present in previous index but no longer on disk |
| Validation | mtime precision of 1 second is used as the safe cross-platform minimum (research/architecture.md §4.5) [VERIFIED] |
| Auth Required | No |

Acceptance Criteria:
- [ ] Modifying one file in a 500-doc non-git folder → re-index processes exactly that file
- [ ] File with mtime equal to `last_indexed_at` is NOT re-processed (edge of timestamp window)
- [ ] `repo_meta.last_indexed_at` updated after each successful incremental run
- [ ] Re-index of 500 docs with 5 changes completes in under 5 seconds

**SPEC-003: Deleted file cleanup**

| Field | Value |
|-------|-------|
| Description | Remove all index entries (vector chunks in LanceDB and FTS entries in SQLite) belonging to a file that no longer exists in the folder |
| Trigger | A file path present in the previous index is absent from the current filesystem scan |
| Input | File path(s) to delete |
| Output | All chunks with `file_path` matching the deleted file removed from both stores |
| Validation | Deletion is by exact `file_path` match; no wildcard or prefix matching |
| Auth Required | No |

Acceptance Criteria:
- [ ] Delete a file → `search()` returns no results from that file
- [ ] Deletion removes entries from both LanceDB (vector) and SQLite FTS5 (keyword) stores
- [ ] A file deleted then re-created with the same name is re-indexed cleanly with no duplicate chunks

**SPEC-004: Large diff fallback**

| Field | Value |
|-------|-------|
| Description | If the change set exceeds 1,000 files, skip the incremental path and perform a full rebuild — processing each file individually would be slower than a bulk rebuild at this scale |
| Trigger | Incremental change detection produces a change set larger than the threshold |
| Input | Count of changed files |
| Output | Full rebuild proceeds; a log message records that the fallback was triggered and why |
| Validation | Threshold is configurable via `CODESIGHT_LARGE_DIFF_THRESHOLD` (default: 1,000) |
| Auth Required | No |

Acceptance Criteria:
- [ ] A change set of 1,001 files triggers a full rebuild with a logged message
- [ ] A change set of 1,000 files triggers incremental processing (at the boundary, incremental applies)
- [ ] `CODESIGHT_LARGE_DIFF_THRESHOLD=500` causes the fallback at 501 files

**SPEC-005: Repo metadata tracking**

| Field | Value |
|-------|-------|
| Description | Store and update indexing state in the `repo_meta` SQLite table so incremental detection has a stable reference point across `index()` calls |
| Trigger | Completion of any index operation (full or incremental) |
| Input | Result of the completed index run |
| Output | `repo_meta` updated with `last_indexed_at` (ISO 8601 timestamp) and `last_commit` (git SHA, if applicable) |
| Validation | Update only occurs on successful completion — a failed or interrupted run does not advance the checkpoint |
| Auth Required | No |

Acceptance Criteria:
- [ ] `status()` returns the `last_commit` hash for git repos and `last_indexed_at` for non-git folders
- [ ] An interrupted index run does not update `last_indexed_at` or `last_commit`
- [ ] `index(force_rebuild=True)` still updates `repo_meta` upon completion

## Edge Cases & Failure Modes

**EDGE-001: Merge commit diff**
- Scenario: A git merge commit is the current HEAD, and `last_commit` is on a different branch
- Expected behavior: Diff against the merge base, not just `HEAD~1`, to capture all files changed by the merge
- Error message: none — handled transparently
- Recovery: If merge base is unreachable, fall back to full rebuild with a log warning

**EDGE-002: File renamed (same content)**
- Scenario: A file is renamed but its content is unchanged; mtime on the new path is recent
- Expected behavior: The old path is detected as deleted (chunks removed); the new path is detected as added (file indexed). Content hashing at the chunk level prevents re-embedding identical chunks
- Error message: none
- Recovery: Automatic — content hash deduplication handles this without manual intervention

**EDGE-003: Interrupted re-index**
- Scenario: The process is killed mid-way through an incremental run
- Expected behavior: Partially processed files have their new chunks stored, but `repo_meta` is not updated. The next `index()` call re-detects the same change set and re-processes (possibly re-embedding some chunks that were already written)
- Error message: none — the system recovers automatically on the next run
- Recovery: Content hashing at the chunk level prevents duplicate embeddings from partial runs

**EDGE-004: Binary files in change set**
- Scenario: A binary file (image, compiled artifact) appears in the git diff or has an updated mtime
- Expected behavior: The file is skipped at the extension-filter stage of the parse pipeline, identical to how it would be skipped in a full rebuild
- Error message: none — skipped silently (file extension not in `CODESIGHT_EXTENSIONS`)
- Recovery: None needed

**EDGE-005: First run on a folder with no prior index**
- Scenario: `index()` is called on a folder with no `repo_meta` entry (fresh install or new folder)
- Expected behavior: Full rebuild runs; `repo_meta` is populated for the first time. Subsequent calls use incremental logic
- Error message: none
- Recovery: Automatic — no `last_indexed_at` means the change set is the entire folder

**EDGE-006: Force-push resets git history**
- Scenario: `last_commit` references a commit that no longer exists in the repository (e.g., after a force-push rewrite)
- Expected behavior: The git diff command fails or returns an error; the system falls back to a full rebuild and logs the reason
- Error message: logged — "Could not compute git diff from last commit [hash]: falling back to full rebuild"
- Recovery: Full rebuild restores correct state; `last_commit` is updated to the new HEAD

## Database Changes

| Table | Column | Type | Constraints | Notes |
|-------|--------|------|-------------|-------|
| repo_meta | last_indexed_at | TEXT | NOT NULL | ISO 8601 UTC timestamp; set after every successful index() |
| repo_meta | last_commit | TEXT | NULLABLE | Git SHA (short or full); NULL for non-git folders |

## Key Parameters

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| Large diff threshold | 1,000 files | Full rebuild is cheaper than 1,000+ individual parse/embed cycles at current throughput |
| mtime precision | 1 second | Safe across Linux (ext4), macOS (APFS), Windows (NTFS) filesystems |
| Stale threshold | 60 minutes | Configurable via `CODESIGHT_STALE_MINUTES`; triggers auto-refresh on `search()` |

## Implementation Notes

### Storage Layer Constraints

LanceDB does not support native incremental indexing in the open-source Python SDK (research/stack.md §3.2) [VERIFIED]. Deletions must be performed via file-path-based filter queries against the LanceDB table and the SQLite FTS5 table separately. The SQLite FTS5 `chunks_fts` table is synced via triggers from the `chunks` table — deletions from `chunks` propagate automatically.

### Git Diff Strategy

For git repos, the diff covers the range `[last_commit..HEAD]`. Merge commits are handled by diffing against the merge base rather than `HEAD~1`, which ensures all files introduced by all merged branches are captured. If the diff command fails for any reason (detached HEAD, shallow clone, corrupted `.git`), the error is logged and a full rebuild runs.

### mtime Precision

Filesystem mtime resolution varies: ext4 and APFS provide nanosecond precision; NTFS provides 100ns; FAT32 provides 2s. The 1-second comparison window (research/architecture.md §4.5) [VERIFIED] is conservative enough to be safe across all common filesystems. Files with identical mtime to `last_indexed_at` are not re-processed (the window is exclusive).

## Alternatives Considered

### Alternative A: Filesystem watcher (inotify/FSEvents)

Trade-off: Real-time updates with zero polling latency.
Rejected because: Platform-specific APIs (inotify on Linux, FSEvents on macOS, ReadDirectoryChangesW on Windows) require a background daemon, complex error handling, and significantly more code. Polling on `index()` calls or scheduled cron jobs is simpler and sufficient for consulting deployments where documents change infrequently.

### Alternative B: Hash all files on every check

Trade-off: More accurate than mtime — detects content changes even when mtime is unchanged (e.g., file copied with preserved mtime).
Rejected because: Requires reading every file to compute the hash, defeating the performance purpose of incremental detection. mtime is fast enough, and chunk-level content hashing already handles the edge case of mtime changing without content change (prevents re-embedding).

## Open Questions

- [ ] Should `status()` report the list of files changed since the last index, or only the timestamp/commit? List is more informative for debugging but adds overhead — @juan
- [ ] For non-git folders, store per-file mtimes in a new `file_meta` table or just a single `last_indexed_at`? Per-file is more precise but requires an additional table migration — @juan

## Acceptance Criteria

- [ ] Modify one file in a 500-doc git repo → only that file is parsed, chunked, embedded; `search()` returns updated content from that file
- [ ] Modify one file in a 500-doc non-git folder → only that file is processed
- [ ] Delete a file → `search()` returns no results from that file
- [ ] `index(force_rebuild=True)` triggers a full rebuild, ignoring incremental logic
- [ ] Git repo: change detection uses `git diff --name-only`, not filesystem scanning
- [ ] Non-git folder: change detection uses mtime comparison (research/architecture.md §4.5) [VERIFIED]
- [ ] Re-index of 500 docs with 5 changes completes in under 5 seconds
- [ ] Change set > 1,000 files → full rebuild triggered with a log message explaining why
- [ ] `status()` reports `last_commit` (git) or `last_indexed_at` (non-git) from `repo_meta`
- [ ] Interrupted re-index does not corrupt the index — next run recovers cleanly
