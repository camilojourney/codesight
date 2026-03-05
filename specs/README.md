# Specs — codesight

Feature specifications for codesight.

## Feature Specs

| # | Spec | Status | Phase |
|---|------|--------|-------|
| 000 | [Template](000-template.md) | — | — |
| 001 | [Core Search Engine](001-core-search-tools.md) | Implemented | v0.1 + v0.2 |
| 002 | [Embedding Model Config](002-embedding-model-config.md) | Done | v0.3 |
| 003 | [Incremental Refresh](003-incremental-refresh.md) | Draft | v0.5 |
| 004 | [AST-Based Code Chunking (tree-sitter)](004-tree-sitter-chunking.md) | Draft | v0.4 |
| 005 | [Automatic Re-indexing](005-watch-unwatch-tools.md) | Deprecated | — |
| 006 | [Pluggable LLM Backend](006-pluggable-llm-backend.md) | Done | v0.3 |
| 007 | [Cross-Encoder Reranking](007-cross-encoder-reranking.md) | Done | v0.3 |
| 008 | [Docker + FastAPI Deployment](008-docker-deployment-fastapi.md) | Draft | v0.8 |
| 009 | [Benchmark Harness](009-benchmark-harness.md) | Draft | v0.4 |
| 010 | [Verification Loops](010-verification-loops.md) | Draft | v0.4 |

## Implementation History

### v0.1 — Hybrid Code Search (completed)
Hybrid BM25 + vector + RRF search engine. Language-aware chunking for 10 languages. Local embeddings. Content hash deduplication. See [Spec 001](001-core-search-tools.md).

### v0.2 — Enterprise Document Search (completed)
Major pivot from MCP code search server to enterprise document search engine:
- Package renamed `semantic_search_mcp` → `codesight`
- MCP layer removed, Python API created (`CodeSight` class)
- Document parsers: PDF, DOCX, PPTX
- Claude answer synthesis via Anthropic API
- Streamlit web chat UI + CLI
- See [Spec 001](001-core-search-tools.md) (updated to cover v0.2)

### v0.3 — Pluggable LLM + Better Embeddings + Reranking (completed)
- Pluggable LLM backend: Claude, Azure OpenAI, OpenAI, Ollama — [Spec 006](006-pluggable-llm-backend.md)
- Configurable embedding model + optional API embeddings (OpenAI) — [Spec 002](002-embedding-model-config.md)
- Optional cross-encoder reranking after RRF for better precision — [Spec 007](007-cross-encoder-reranking.md)

### v0.4 — Benchmark Harness + Verification Loops (planned)
- Reproducible benchmark framework: 80 queries, DeepEval + RAGAS, SQLite results — [Spec 009](009-benchmark-harness.md)
- HHEM hallucination detection, Claude Citations, confidence gates — [Spec 010](010-verification-loops.md)
- AST-based code chunking with tree-sitter for 10 languages — [Spec 004](004-tree-sitter-chunking.md)

### v0.5 — Adaptive Architecture (planned)
- Incremental refresh: git diff + mtime change detection — [Spec 003](003-incremental-refresh.md)
- Semantic cache, query router, CAG path (specs TBD)

### v0.8 — Deployment & Scaling (planned)
- Docker deployment, FastAPI server, auth, web chat UI for 50+ concurrent users — [Spec 008](008-docker-deployment-fastapi.md)

> For design decisions (why LanceDB, why hybrid RRF, etc.), see `docs/decisions/`.
> For project roadmap, see `docs/roadmap.md`.
> For client pitch preparation, see `docs/playbooks/client-pitch.md`.
