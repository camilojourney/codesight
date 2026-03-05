# Spec 011: Microsoft 365 Graph Connector

**Status:** planned
**Phase:** v0.6
**Research deps:** research/architecture.md §5 (Recommended Architecture)
**Depends on:** Spec 001 (core search engine), Spec 002 (embedding config)
**Blocks:** Spec 012 (Teams bot needs indexed M365 content)
**Author:** Juan Martinez
**Created:** 2026-03-04
**Updated:** 2026-03-04

## Problem

CodeSight currently indexes local folders only. But in real consulting engagements (and for Juan's own student account), documents live in Microsoft 365 — OneDrive files, Outlook emails, OneNote notebooks, SharePoint sites. Users must manually download files to a local folder before CodeSight can index them, which means:

- Documents go stale immediately (the local copy diverges from M365)
- Emails and OneNote pages can't be indexed at all (no file export)
- The setup friction kills the pilot experience ("just point it at your docs" becomes "export everything first")

Microsoft Graph API provides unified REST access to all M365 data with OAuth2 authentication. A connector that pulls content directly from Graph API into the existing indexing pipeline removes the export step entirely.

## Goals

- Pull documents from OneDrive, SharePoint, Outlook, and OneNote via Microsoft Graph API
- OAuth2 authentication flow (delegated permissions — user signs in, app reads their data)
- Incremental sync using Graph API delta queries (only fetch changes since last sync)
- Store fetched content as local files in a managed cache directory, then index with existing pipeline
- Works with M365 Education (student accounts), Business, and Enterprise tenants
- Single `codesight sync` CLI command to pull and index in one step

## Non-Goals

- Write-back to M365 (read-only connector) — we never modify the user's data
- Real-time webhooks for instant sync — delta queries on `codesight sync` are sufficient for v0.6
- Teams chat message indexing — handled separately in Spec 012
- Calendar event indexing — low value for document search
- Admin consent / application permissions — delegated (user) permissions only for now

## Solution

### Architecture

```
User runs: codesight sync --source m365

    +-----------------+
    | M365 Graph API  |
    | (Microsoft)     |
    +--------+--------+
             |  OAuth2 token
             v
    +--------+--------+
    | GraphConnector   |   <-- NEW: src/codesight/connectors/m365.py
    |                  |
    | - authenticate() |   MSAL library, device code flow
    | - sync_drive()   |   OneDrive / SharePoint files
    | - sync_mail()    |   Outlook messages → .eml or .txt
    | - sync_notes()   |   OneNote pages → .html or .md
    | - delta_state()  |   Track sync cursor per source
    +--------+---------+
             |  writes files to cache
             v
    ~/.codesight/m365-cache/<tenant_hash>/
    ├── drive/          ← OneDrive/SharePoint files (PDF, DOCX, etc.)
    ├── mail/           ← Emails as .txt (from + subject + body)
    └── notes/          ← OneNote pages as .md

             |  then calls existing pipeline
             v
    CodeSight.index(cache_dir)   ← existing pipeline, no changes needed
```

### Authentication

Use MSAL (Microsoft Authentication Library) with **device code flow** — works in CLI without a browser redirect server:

1. User runs `codesight sync --source m365`
2. App prints: "Go to https://microsoft.com/devicelogin and enter code ABCD1234"
3. User signs in with their M365 account in browser
4. App receives OAuth2 token with delegated permissions
5. Token cached in `~/.codesight/m365-token-cache.json` (encrypted at rest)

**Required delegated permissions:**
- `Files.Read` — OneDrive files
- `Sites.Read.All` — SharePoint sites
- `Mail.Read` — Outlook emails
- `Notes.Read` — OneNote notebooks
- `User.Read` — basic profile (for tenant identification)

### Data Sources

#### OneDrive / SharePoint Files
```
GET /me/drive/root/delta  → incremental file list
GET /me/drive/items/{id}/content  → download file bytes

Supported: PDF, DOCX, PPTX, TXT, MD (match INDEXABLE_EXTENSIONS from config.py)
Skip: images, videos, executables, archives
```

#### Outlook Email
```
GET /me/messages?$select=subject,from,body,receivedDateTime&$top=100
GET /me/messages/delta  → incremental

Convert to indexable text:
  From: sender@example.com
  Subject: Q3 Budget Review
  Date: 2026-03-01
  ---
  [body as plain text]

Save as: mail/<message_id>.txt
```

#### OneNote Pages
```
GET /me/onenote/pages?$select=title,contentUrl&$top=100
GET /me/onenote/pages/{id}/content  → HTML

Convert HTML → Markdown (html2text library)
Save as: notes/<page_id>.md
```

### Incremental Sync (Delta Queries)

Microsoft Graph supports delta queries that return only changes since last sync:

```python
# First sync: GET /me/drive/root/delta → full file list + deltaLink
# Next sync:  GET {deltaLink} → only changed/added/deleted files

# Store delta cursors in SQLite:
# ~/.codesight/data/<hash>/metadata.db → m365_sync_state table
#   source_type | delta_link | last_synced_at
```

### Key Parameters

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| `CODESIGHT_M365_CLIENT_ID` | Azure AD app ID | Registered in Azure portal |
| `CODESIGHT_M365_TENANT_ID` | `common` (default) | `common` works for any tenant; can be scoped to specific org |
| `CODESIGHT_M365_SCOPES` | `Files.Read Mail.Read Notes.Read Sites.Read.All User.Read` | Minimum permissions for read-only access |
| Max email fetch | 500 messages | Reasonable for initial index; paginate with `$top` + `$skip` |
| Max file size | 50 MB | Graph API limit for single file download |
| Token cache path | `~/.codesight/m365-token-cache.json` | Persists across sessions, auto-refresh |

### Dependencies

- `msal>=1.28` — Microsoft Authentication Library for Python
- `httpx>=0.27` — async HTTP client for Graph API calls (already fast, good error handling)
- `html2text>=2024.2` — OneNote HTML → Markdown conversion
- Depends on: Spec 001 (indexing pipeline), Spec 002 (embedding)
- Depended on by: Spec 012 (Teams bot indexes M365 content)

## Implementation Notes

### File Structure

```
src/codesight/connectors/
├── __init__.py
├── m365.py          ← GraphConnector class
└── m365_auth.py     ← MSAL auth flow + token cache
```

### SPEC Behaviors

- **SPEC-011-001:** Device code OAuth2 flow authenticates user and caches token.
- **SPEC-011-002:** OneDrive/SharePoint files synced to local cache filtered by INDEXABLE_EXTENSIONS.
- **SPEC-011-003:** Outlook emails converted to plain text with metadata headers and saved as .txt.
- **SPEC-011-004:** OneNote pages fetched as HTML, converted to Markdown, saved as .md.
- **SPEC-011-005:** Delta queries track sync state per source; subsequent syncs only fetch changes.
- **SPEC-011-006:** After sync, existing `CodeSight.index()` pipeline indexes the cache directory.
- **SPEC-011-007:** CLI `codesight sync --source m365` orchestrates auth + sync + index.

## Edge Cases & Failure Modes

- **EDGE-011-001:** Token expired mid-sync — MSAL auto-refreshes; if refresh fails, re-prompt device code flow.
- **EDGE-011-002:** File too large (>50MB) — skip with warning log, continue syncing other files.
- **EDGE-011-003:** OneNote page with only images/no text — skip (no indexable content).
- **EDGE-011-004:** Tenant blocks app registration — error message: "Your organization's admin must allow app registrations. Contact your IT department."
- **EDGE-011-005:** No internet during sync — fail fast with clear error, preserve existing cache/index.
- **EDGE-011-006:** Email with only attachments, no body — index attachments if they match INDEXABLE_EXTENSIONS.
- **EDGE-011-007:** SharePoint site permissions denied — skip site, log warning, continue with accessible sites.
- **EDGE-011-008:** Delta link expired (>30 days since last sync) — fall back to full sync.

## Alternatives Considered

### Alternative A: Microsoft Graph SDK for Python (`msgraph-sdk`)

Trade-off: Official SDK, auto-generated from OpenAPI spec, full type safety.
Rejected because: The SDK is massive (>100MB), has many transitive dependencies, and the auto-generated code is harder to debug. Direct `httpx` calls to Graph REST API are simpler, smaller, and we only need 5-6 endpoints.

### Alternative B: Download files to temp dir, index, delete

Trade-off: No persistent cache, saves disk space.
Rejected because: Every sync would re-download and re-index all files. The cache + content-hash dedup means subsequent syncs are fast (only changed files re-index).

## Observability

- Log: `m365.sync.start` with source types and tenant ID
- Log: `m365.sync.complete` with file counts per source type and duration
- Log: `m365.sync.skip` for each skipped file (too large, unsupported type, permission denied)
- Log: `m365.auth.device_code` when device code flow starts
- Log: `m365.auth.token_refresh` when token auto-refreshes
- Metric: files synced per source type, total bytes, sync duration

## Acceptance Criteria

- [ ] `codesight sync --source m365` authenticates via device code flow on first run
- [ ] Subsequent runs reuse cached token without re-authentication
- [ ] OneDrive files (PDF, DOCX, PPTX, TXT, MD) downloaded and indexed
- [ ] Outlook emails (last 500) converted to text and indexed
- [ ] OneNote pages converted to Markdown and indexed
- [ ] Delta sync only fetches changes since last sync (verified by mock)
- [ ] Files exceeding 50MB are skipped with warning
- [ ] Expired token triggers automatic refresh or re-auth prompt
- [ ] `codesight search "query"` returns results from M365-sourced documents
- [ ] `codesight ask "question"` answers from M365-sourced content with citations
- [ ] Works with M365 Education (student) accounts
- [ ] Tests pass with mocked Graph API responses (no real M365 calls in CI)
