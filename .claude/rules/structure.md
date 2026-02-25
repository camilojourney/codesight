# Repository Structure — codesight

> WHERE things go in this repo. Read before creating or moving any file.
> Type D (early-stage CLI tool) — minimal structure until features require more.

## Root Level

| File | Purpose |
|------|---------|
| `CLAUDE.md` | Claude Code auto-loads. Commands + critical rules only (≤80 lines). |
| `AGENTS.md` | Agent role, permissions, doc pointer index. |
| `README.md` | Quick start, tool reference, architecture summary. |
| `ARCHITECTURE.md` | Codebase tour — components, data flow, what not to change. |
| `justfile` | Unified task runner (`just --list` to discover commands). |
| `pyproject.toml` | Python package config. Package name: `semantic_search_mcp`. |
| `.env.example` | Environment variable template. |
| `.gitignore` | Standard patterns + data/ directory. |

**Never create files at root** unless they are one of the above + `LICENSE`.

## Source Code (`src/semantic_search_mcp/`)

All production code lives here. Package name is `semantic_search_mcp` — do not rename.

| File | Purpose |
|------|---------|
| `server.py` | MCP tool registration only. No business logic here. |
| `indexer.py` | Index pipeline orchestration. |
| `search.py` | Retrieval logic (BM25 + vector + RRF). |
| `chunker.py` | Language-aware text splitting. |
| `embeddings.py` | Embedding model wrapper. |
| `store.py` | LanceDB + SQLite dual-write. |
| `config.py` | Pydantic settings from env. |
| `git_utils.py` | .gitignore-aware file walking. |
| `types.py` | Shared Pydantic models. |

New modules go here. Never add business logic to `server.py`.

## Tests (`tests/`)

| Pattern | Purpose |
|---------|---------|
| `tests/test_<module>.py` | Unit tests mirroring `src/` structure |
| `tests/conftest.py` | Shared fixtures |

## Docs (`docs/`)

**Exactly four categories — no others.**

| Path | Purpose |
|------|---------|
| `docs/README.md` | Navigation index. |
| `docs/vision.md` | Product vision. Update at most yearly. |
| `docs/roadmap.md` | Versioned feature plan. |
| `docs/decisions/NNNN-*.md` | ADRs — immutable once accepted. |
| `docs/playbooks/*.md` | Step-by-step operational guides. |

**NEVER create** `docs/architecture.md`, `docs/deployment.md`, `docs/notes.md` or any other ad-hoc files.
Architecture → `ARCHITECTURE.md` (root). Specs → `specs/`. Everything else → the four categories above.

## Specs (`specs/`)

Numbered implementation specs. Primary deliverable for this repo.
Flat structure only — no subdirectories.

## What Goes Where

| Content | Location |
|---------|----------|
| New feature spec | `specs/NNN-name.md` |
| Architecture decision | `docs/decisions/NNNN-name.md` |
| Dev setup guide | `docs/playbooks/development.md` |
| Session notes | `devlog/YYYY-MM-DD.md` |
| Agent priorities | `.self-improvement/NEXT.md` |
| Worker reports | `.self-improvement/reports/<worker>/YYYY-MM-DD.md` |
