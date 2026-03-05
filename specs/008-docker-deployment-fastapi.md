# Spec 008: Docker Deployment + FastAPI Production Server

**Status:** draft
**Phase:** v0.8
**Research deps:** research/stack.md §5 (Deployment Infrastructure), research/architecture.md §4.1 (Two-Loop Architecture — deployment patterns), research/benchmarks.md §2 (Latency targets — P50/P95)
**Depends on:** Spec 001 (core search engine), Spec 006 (pluggable LLM backend — configured via environment variables)
**Blocks:** none
**Created:** 2026-02-28
**Updated:** 2026-03-04

## Problem

The Streamlit web chat UI works for demos and small teams (1-5 users) but has fundamental limitations for production consulting deployments:

- Streamlit is single-threaded — it cannot serve 20+ concurrent users without lag
- No REST API — other tools cannot call CodeSight programmatically
- No authentication — anyone who can reach the URL can search all indexed documents
- No standard deployment artifact — each client deployment requires manual setup

When a consultant deploys CodeSight for a 50-person team on the client's cloud (Azure, AWS, GCP), they need a Docker image they can `docker run` and a production HTTP server that handles concurrent users. The end product for clients remains a web chat UI — they type questions and get answers. FastAPI is the backend that serves this UI and handles concurrent requests.

## Goals

- Single-command deployment: `docker run codesight` with environment variables for configuration
- FastAPI backend serving the CodeSight API over HTTP, with a minimal web chat UI
- Handle 50 concurrent users without degradation; P50 search latency under 500ms per concurrent request (research/benchmarks.md §2) [VERIFIED]
- API key authentication on all `/api/*` endpoints
- Documents mounted as a read-only volume — the container cannot modify source files under any circumstances
- Index persists across container restarts via Docker volume
- Works with all LLM backends: Claude, Azure OpenAI, OpenAI, Ollama (research/stack.md §2.2) [VERIFIED]
- Health and readiness endpoints for cloud deployment lifecycle management (research/stack.md §5.2) [VERIFIED]

## Non-Goals

- SSO / OAuth / SAML — planned for v1.0
- Multi-tenant indexes (separate index per user or team) — one index per deployment
- Kubernetes / Helm charts — Docker is sufficient for consulting deployments at this scale
- Custom React or Vue frontend — minimal HTML/JS chat UI served directly by FastAPI
- SQLite-to-PostgreSQL migration — SQLite + LanceDB scale appropriately for single-server deployments
- WebSocket streaming — SSE streaming for RAG responses is planned for v0.8 separately (research/stack.md §5.2) [VERIFIED]; this spec covers the core HTTP API and container

## Solution

A FastAPI server runs inside a Docker container, exposing the CodeSight Python API over HTTP. The container mounts two volumes: the client's documents as read-only (`/data`), and the search index as persistent read-write (`/index`). Authentication is enforced by middleware on all `/api/*` endpoints via a secret API key. The web chat UI is a static HTML/JS page served from FastAPI — no build step, no npm, no React.

```
Browser (client's team)
    │
    ▼
[Docker container on client's cloud/on-prem server]
┌────────────────────────────────────────────────────┐
│  FastAPI (uvicorn, port 8000)                       │
│                                                     │
│  GET  /              → web chat UI (static HTML)    │
│  POST /api/search    → CodeSight.search()           │
│  POST /api/ask       → CodeSight.ask()              │
│  POST /api/index     → CodeSight.index()            │
│  GET  /api/status    → CodeSight.status()           │
│  GET  /health        → liveness probe               │
│  GET  /ready         → readiness probe              │
│                                                     │
│  Auth middleware: X-API-Key header on /api/*        │
│  CodeSight engine (shared instance, in-process)     │
│  LanceDB + SQLite stored in /index volume           │
└────────────────────────────────────────────────────┘
    │                         │
  /data (read-only)       /index (persistent volume)
  Client's documents      Search index (LanceDB + SQLite)
```

Deployment workflow for a consultant:
1. Build the Docker image (or pull from a registry)
2. Run with the client's document folder mounted read-only at `/data`
3. Pass LLM backend credentials and the API key as environment variables
4. The client opens their browser and interacts with the chat UI — no technical steps required from them

## Core Specifications

**SPEC-001: Docker image builds and starts**

| Field | Value |
|-------|-------|
| Description | A single `Dockerfile` at the repo root produces a self-contained image that runs the FastAPI server with all dependencies and the embedding model pre-downloaded |
| Trigger | `docker build` followed by `docker run` with required environment variables |
| Input | `CODESIGHT_API_KEY` env var, volume mounts at `/data` and `/index`, LLM backend env vars |
| Output | FastAPI server listening on port 8000; `/ready` returns 200 when the engine is initialized |
| Validation | Image is based on `python:3.12-slim` (research/stack.md §5.2) [VERIFIED]; runs as a non-root user; embedding model pre-downloaded at build time so no internet access is required at runtime |
| Auth Required | No (container startup) |

Acceptance Criteria:
- [ ] `docker build -t codesight .` completes without errors
- [ ] `docker run` with a mounted document folder starts the server on port 8000
- [ ] The embedding model is baked into the image — no download on first run
- [ ] Container runs as a non-root user (research/stack.md §5.2) [VERIFIED]
- [ ] `GET /ready` returns 200 within 30 seconds of container start

**SPEC-002: FastAPI HTTP endpoints**

| Field | Value |
|-------|-------|
| Description | Four API endpoints expose the CodeSight Python API over HTTP: search, ask, index, and status |
| Trigger | HTTP requests to `/api/*` with a valid `X-API-Key` header |
| Input | JSON request body per endpoint (see API Contract below) |
| Output | JSON response per endpoint |
| Validation | Empty `query` or `question` fields return 400; missing or invalid `X-API-Key` returns 401 |
| Auth Required | Yes — `X-API-Key` header or `Authorization: Bearer <key>` |

Acceptance Criteria:
- [ ] `POST /api/search` returns ranked search results as JSON
- [ ] `POST /api/ask` returns `{text, sources, model}` as JSON
- [ ] `POST /api/index` triggers indexing and returns `{total_files, total_chunks, duration_seconds}`
- [ ] `GET /api/status` returns `{indexed, total_files, total_chunks, last_indexed_at, is_stale}`
- [ ] All `/api/*` endpoints return 401 for missing or invalid API key
- [ ] `POST /api/search` with empty `query` returns 400
- [ ] 50 concurrent `/api/search` requests complete with P50 latency under 500ms (research/benchmarks.md §2) [VERIFIED]

**SPEC-003: API key authentication middleware**

| Field | Value |
|-------|-------|
| Description | An HTTP middleware layer enforces API key authentication on all `/api/*` routes; the web UI at `/` and health endpoints are exempt |
| Trigger | Every inbound HTTP request to `/api/*` |
| Input | `X-API-Key` header value or `Authorization: Bearer <key>` value |
| Output | Request proceeds if key matches `CODESIGHT_API_KEY`; 401 JSON response if not |
| Validation | If `CODESIGHT_API_KEY` is not set in the environment, auth is disabled and a startup warning is logged: `"Running without auth — set CODESIGHT_API_KEY for production"` |
| Auth Required | Yes (the middleware enforces this) |

Acceptance Criteria:
- [ ] Requests to `/api/search` without `X-API-Key` return 401 `{"error": "Invalid or missing API key"}`
- [ ] Requests with correct `X-API-Key` succeed
- [ ] `GET /` (web chat UI) does not require authentication
- [ ] `GET /health` and `GET /ready` do not require authentication
- [ ] When `CODESIGHT_API_KEY` is unset, all requests succeed and a warning is logged at startup

**SPEC-004: Read-only document volume**

| Field | Value |
|-------|-------|
| Description | The document folder is mounted into the container at `/data` with read-only permissions at the OS level; the container cannot write to source documents under any circumstances |
| Trigger | Container startup with `-v /path/to/docs:/data:ro` Docker flag |
| Input | Host filesystem path to client's documents |
| Output | Documents accessible to the indexer at `/data` for reading only |
| Validation | The `:ro` Docker volume flag enforces this at the kernel level — no application-level check is required. The CLAUDE.md read-only invariant (the engine NEVER writes to indexed folders) is preserved by construction. |
| Auth Required | No |

Acceptance Criteria:
- [ ] Container cannot write to `/data` — any write attempt fails at the OS level
- [ ] `POST /api/index` reads from `/data` and writes only to `/index`
- [ ] The read-only invariant from CLAUDE.md is verified: `echo "test" > /data/test.txt` from within the container returns "Read-only file system"

**SPEC-005: Persistent index volume**

| Field | Value |
|-------|-------|
| Description | The search index (LanceDB + SQLite files) is stored in a Docker named volume at `/index` so it persists across container restarts and upgrades |
| Trigger | Container startup with `-v codesight-index:/index` Docker flag |
| Input | Docker named volume |
| Output | Index available immediately on restart without re-indexing |
| Validation | `CODESIGHT_DATA_DIR=/index` is set in the Dockerfile ENV so the engine writes to the volume by default |
| Auth Required | No |

Acceptance Criteria:
- [ ] Index survives container restart — `GET /api/status` returns `indexed: true` immediately after restart
- [ ] No re-indexing required after a normal container stop/start cycle
- [ ] `CODESIGHT_DATA_DIR` defaults to `/index` in the image

**SPEC-006: Health and readiness endpoints**

| Field | Value |
|-------|-------|
| Description | Two HTTP endpoints support cloud deployment health checks: `/health` for liveness (is the process alive?) and `/ready` for readiness (is the engine initialized and able to serve requests?) |
| Trigger | HTTP GET requests to `/health` or `/ready` |
| Input | None |
| Output | 200 JSON `{"status": "ok"}` when healthy/ready; 503 JSON `{"status": "not ready"}` if the engine is still initializing |
| Validation | `/health` always returns 200 if the process is running; `/ready` returns 503 until the CodeSight engine has completed its first initialization (research/stack.md §5.2) [VERIFIED] |
| Auth Required | No — health checks must be accessible without auth for load balancers |

Acceptance Criteria:
- [ ] `GET /health` returns 200 immediately after the process starts
- [ ] `GET /ready` returns 503 while the engine initializes and 200 once ready
- [ ] Both endpoints are accessible without an API key

**SPEC-007: Concurrent request handling**

| Field | Value |
|-------|-------|
| Description | The server handles concurrent search and ask requests without serialization; the CodeSight engine instance is shared across workers using async request handling |
| Trigger | Multiple simultaneous HTTP requests to `/api/search` or `/api/ask` |
| Input | Concurrent HTTP requests |
| Output | Each request handled independently; results correct for each |
| Validation | Uvicorn workers: `(2 × CPU cores) + 1`, bounded by available RAM (research/stack.md §5.2) [VERIFIED]. Default: 4 workers on a 2-core VM (handles ~50 concurrent users). `--limit-max-requests=1000` with jitter prevents ML memory leaks (research/stack.md §5.2) [VERIFIED] |
| Auth Required | Yes (via SPEC-003) |

Acceptance Criteria:
- [ ] 50 concurrent `/api/search` requests complete without errors
- [ ] P50 latency for concurrent search requests is under 500ms (research/benchmarks.md §2) [VERIFIED]
- [ ] Concurrent `/api/ask` requests each receive the correct independent response
- [ ] `--limit-max-requests=1000` is set in the uvicorn startup command

**SPEC-008: Web chat UI**

| Field | Value |
|-------|-------|
| Description | A minimal HTML/JS chat page served from `GET /` that allows users to ask questions and see answers with source citations — no build step, no npm, no React |
| Trigger | Browser navigates to the server URL |
| Input | None (static HTML served) |
| Output | Chat interface with question input, message history, and expandable source cards per answer |
| Validation | The UI includes the API key in its fetch calls (configured via a `/config` endpoint or embedded at serve-time). Streamlit remains available for local development via `python -m codesight demo` |
| Auth Required | No (the UI itself is public; its API calls use the API key internally) |

Acceptance Criteria:
- [ ] `GET /` serves a functional chat UI without authentication
- [ ] A user can type a question in the browser and receive an answer with source citations
- [ ] Source citations are expandable (show file path, line range, snippet)
- [ ] The UI works on mobile (responsive layout)

## API Contract

```
POST /api/search
  Auth: X-API-Key header required

  Request:
    query: string — search query (required, non-empty)
    top_k: integer — number of results (optional, default: 8)
    file_glob: string | null — optional file filter (optional)

  Response (200):
    results: array of SearchResult
      - file_path: string
      - start_line: integer
      - end_line: integer
      - score: float
      - content: string (chunk text, not full file)

  Errors:
    400 — empty query
    401 — missing or invalid API key


POST /api/ask
  Auth: X-API-Key header required

  Request:
    question: string — natural language question (required, non-empty)
    top_k: integer — chunks to use for context (optional, default: 5)

  Response (200):
    text: string — LLM-generated answer
    sources: array of SearchResult — chunks that informed the answer
    model: string — LLM backend + model name used

  Errors:
    400 — empty question
    401 — missing or invalid API key
    503 — LLM backend unavailable (Ollama not running, API key invalid, network error)


POST /api/index
  Auth: X-API-Key header required

  Request:
    force_rebuild: boolean — full rebuild vs incremental (optional, default: false)

  Response (200):
    total_files: integer
    total_chunks: integer
    duration_seconds: float

  Errors:
    401 — missing or invalid API key
    409 — indexing already in progress (concurrent request lock)


GET /api/status
  Auth: X-API-Key header required

  Response (200):
    indexed: boolean
    total_files: integer
    total_chunks: integer
    last_indexed_at: string | null — ISO 8601 timestamp
    is_stale: boolean

  Errors:
    401 — missing or invalid API key


GET /
  Auth: none
  Response (200): HTML — web chat UI


GET /health
  Auth: none
  Response (200): {"status": "ok"}


GET /ready
  Auth: none
  Response (200): {"status": "ok"} — engine initialized
  Response (503): {"status": "not ready"} — engine still initializing
```

## Edge Cases & Failure Modes

**EDGE-001: Documents folder empty at startup**
- Scenario: The container starts with an empty `/data` volume or no volume mounted at `/data`
- Expected behavior: `GET /ready` returns 200 (the engine initializes with an empty index). `POST /api/index` returns `{total_files: 0, total_chunks: 0}`. `POST /api/search` returns empty results. `POST /api/ask` returns a message indicating no documents are indexed.
- Error message: `{"text": "No documents are indexed. Mount your documents at /data and call /api/index."}`
- Recovery: Mount the documents volume and call `POST /api/index`

**EDGE-002: API key not set**
- Scenario: `CODESIGHT_API_KEY` environment variable is absent
- Expected behavior: Auth middleware is disabled; all requests succeed. A warning is logged at startup.
- Error message: `"WARNING: CODESIGHT_API_KEY not set — running without authentication. Set this variable before production deployment."`
- Recovery: Set `CODESIGHT_API_KEY` in the `docker run` environment

**EDGE-003: Document volume not mounted**
- Scenario: The container starts without the `-v /path/to/docs:/data:ro` flag
- Expected behavior: The indexer finds no files at `/data`; `POST /api/index` returns zero files with a clear message
- Error message: `{"detail": "No documents found at /data. Mount your document folder: -v /path/to/docs:/data:ro"}`
- Recovery: Restart the container with the correct `-v` flag

**EDGE-004: Concurrent index requests**
- Scenario: Two callers send `POST /api/index` simultaneously
- Expected behavior: The first request acquires an in-process lock and proceeds. The second request immediately receives 409.
- Error message: `{"error": "Indexing already in progress. Retry after the current operation completes."}`
- Recovery: Caller retries after the first index completes (check via `GET /api/status`)

**EDGE-005: LLM backend unavailable**
- Scenario: `POST /api/ask` is called but the configured LLM backend is unreachable (Ollama not running, API key invalid, network error)
- Expected behavior: The search step completes successfully. The LLM synthesis step returns 503 with the raw retrieved chunks included so the caller can still see the source material.
- Error message: `{"error": "LLM backend unavailable: <backend-specific reason>", "sources": [...]}`
- Recovery: Fix the LLM backend configuration and retry; or use `POST /api/search` for keyword-only retrieval without LLM synthesis

**EDGE-006: Oversized file in indexed folder**
- Scenario: A file larger than the configured `CODESIGHT_MAX_FILE_MB` limit (default: 50MB) is present in `/data`
- Expected behavior: The file is skipped during indexing with a warning log; all other files index normally
- Error message: logged — `"Skipping {file_path}: file size {size}MB exceeds limit {limit}MB"`
- Recovery: Increase the limit via `CODESIGHT_MAX_FILE_MB` env var or remove the file from the mounted folder

## Key Parameters

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| Server port | 8000 | Standard for FastAPI/uvicorn; configurable via `PORT` env var |
| Uvicorn workers | `(2 × CPU cores) + 1`, default 4 | Worker formula for CPU-bound services (research/stack.md §5.2) [VERIFIED]; 4 workers handles ~50 concurrent users on a 2-core VM |
| Max requests per worker | 1,000 (with jitter) | Prevents ML memory leaks from long-lived workers (research/stack.md §5.2) [VERIFIED] |
| Request timeout | 60 seconds | `ask()` can take 5-30s for LLM synthesis; search alone is <1s |
| Max request body | 1MB | Queries and questions are small text; prevents accidental abuse |
| Base image | `python:3.12-slim` | Python 3.12 provides ~5% performance improvement over 3.11 (research/stack.md §5.2) [VERIFIED] |
| CODESIGHT_DATA_DIR | `/index` (default in image) | Separates the index from the read-only document mount |

## Implementation Notes

### New Files

| File | Purpose |
|------|---------|
| `Dockerfile` | Container build definition |
| `docker-compose.yml` | Dev/demo compose with example configuration and volume mounts |
| `src/codesight/web/server.py` | FastAPI app, route handlers, auth middleware, concurrent index lock |
| `src/codesight/web/static/index.html` | Single-page chat UI (HTML + inline JS + inline CSS) |

### Optional Dependency Group

The FastAPI server dependencies are added as an optional `[server]` extra in `pyproject.toml` so the core library can be installed without the server dependencies:

- `fastapi>=0.135.0` (required for native SSE support — research/stack.md §5.2) [VERIFIED]
- `uvicorn>=0.30`

### Uvicorn Configuration

Uvicorn is started with `fastapi run` (the official recommended approach as of FastAPI 0.110+ — research/stack.md §5.4) [VERIFIED] rather than directly calling `uvicorn`. Key flags: `--workers`, `--limit-max-requests=1000`, `--host 0.0.0.0`, `--port 8000`.

### Streaming (Future)

This spec covers synchronous HTTP only. SSE streaming for `ask()` responses is a v0.8 enhancement covered separately. The `fastapi.sse` module (FastAPI 0.135.0+, research/stack.md §5.2) [VERIFIED] is available for the follow-up spec.

## Alternatives Considered

### Alternative A: Keep Streamlit, add nginx reverse proxy

Trade-off: Simpler — reuses existing UI code.
Rejected because: Streamlit's single-threaded model serializes requests, limiting throughput for concurrent users. A proper REST API is needed for programmatic access by other tools. FastAPI handles async natively and auto-generates OpenAPI docs.

### Alternative B: Flask instead of FastAPI

Trade-off: Simpler, more familiar to many Python developers.
Rejected because: Flask is synchronous by default — async request handling requires extensions. FastAPI gives native async (important for concurrent LLM calls), Pydantic validation, and OpenAPI docs for free (research/stack.md §5.2) [VERIFIED].

### Alternative C: Full React or Vue frontend

Trade-off: Better UX, component ecosystem, progressive enhancement.
Rejected because: The primary interaction is "type question, read answer." A static HTML page with fetch calls is sufficient for v0.8. If clients want a custom frontend, the REST API (SPEC-002) supports it. A build step (npm, bundler) adds complexity the consultant deployment workflow doesn't need.

## Observability

- Structured JSON logging via Python `logging` (uvicorn default output format)
- Log events at: container startup, engine initialization complete, each `index()` start/complete, each `search()` call, each `ask()` call, each error
- Request timing logged for every `/api/*` response
- `GET /api/status` doubles as a health check and monitoring probe
- `GET /health` and `GET /ready` support cloud load balancer health checks

## Rollback Plan

Docker deployment is stateless from the application layer — the index is in a named volume and documents are mounted read-only. Rollback:
1. Stop the container
2. Pull or build the previous image version
3. Start the container with the same volume mounts
4. The existing index is intact in the `/index` volume — no re-indexing needed

If the index is corrupted by a failed upgrade: delete the `/index` volume, start the container, and call `POST /api/index` to rebuild. No source documents are lost (they are in the read-only `/data` mount).

## Open Questions

- [ ] Should `POST /api/index` be admin-only via a separate `CODESIGHT_ADMIN_KEY`? Prevents regular users from triggering expensive rebuilds — @juan
- [ ] Docker image size: the embedding model adds ~270-500MB depending on model. Pre-bake into image (deterministic, no first-run latency) vs download at first run (smaller image, requires internet on first start) — @juan
- [ ] Should the static chat UI be embedded in the Python package or served from a separate `static/` directory? Embedded is simpler; separate is easier to customize per client — @juan

## Acceptance Criteria

- [ ] `docker build -t codesight .` builds successfully with embedding model pre-downloaded
- [ ] `docker run` with mounted documents starts FastAPI on port 8000
- [ ] `GET /` serves the web chat UI — user can type a question and receive an answer
- [ ] `POST /api/search` returns ranked results as JSON
- [ ] `POST /api/ask` returns answer with text and sources as JSON
- [ ] `POST /api/index` triggers indexing and returns file/chunk counts
- [ ] `GET /api/status` returns index stats as JSON
- [ ] All `/api/*` requests without valid `X-API-Key` return 401
- [ ] 50 concurrent `/api/search` requests complete with P50 latency under 500ms (research/benchmarks.md §2) [VERIFIED]
- [ ] Documents mounted read-only — `echo "test" > /data/test.txt` from within the container fails with "Read-only file system"
- [ ] Index persists across container restarts via Docker volume
- [ ] Works with all LLM backends (Claude, Azure, OpenAI, Ollama) via environment variables
- [ ] `GET /health` returns 200; `GET /ready` returns 503 while initializing, 200 when ready
- [ ] Container runs as a non-root user (research/stack.md §5.2) [VERIFIED]
