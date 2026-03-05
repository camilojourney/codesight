# Roadmap — codesight

## v0.1 — Hybrid Code Search Engine ✅

- [x] Hybrid BM25 + vector retrieval with RRF merge
- [x] LanceDB vectors + SQLite FTS5 sidecar
- [x] Language-aware regex chunking (10 languages)
- [x] `all-MiniLM-L6-v2` local embeddings (no API key)
- [x] `.gitignore`-aware file walking
- [x] Content hashing (skip unchanged chunks)

## v0.2 — Enterprise Document Search ✅

- [x] Package rename: `semantic_search_mcp` → `codesight`
- [x] Remove MCP layer (server.py, fastmcp dependency)
- [x] Document parsers: PDF (pymupdf), DOCX (python-docx), PPTX (python-pptx)
- [x] Document-aware chunking (paragraph boundaries, page metadata)
- [x] Python API: `CodeSight` class with `index()`, `search()`, `ask()`, `status()`
- [x] Claude answer synthesis: search → context → Claude API → Answer with citations
- [x] Streamlit web chat UI (`demo/app.py`)
- [x] CLI: `python -m codesight index|search|ask|status|demo`
- [x] Auto-index on first search, auto-refresh when stale

## v0.3 — Pluggable LLM + Better Embeddings + Reranking (Next)

- [ ] Pluggable LLM backend: Claude API, Azure OpenAI, OpenAI, Ollama (local)
- [ ] `CODESIGHT_LLM_BACKEND` config: `claude` | `azure` | `openai` | `ollama`
- [ ] Upgrade default embedding model to `nomic-embed-text-v1.5` (768 dims, 8K context)
- [ ] Optional API embedding support (OpenAI, Voyage) via `CODESIGHT_EMBEDDING_BACKEND`
- [ ] Cross-encoder reranker after RRF (MiniLM-L-6-v2 dev → Qwen3-0.6B prod)
- [ ] Configurable embedding model via environment variable (allowlist validation)

## v0.4 — Benchmark Harness + Verification Loops

- [ ] Question bank: 80 queries with human-verified ground truth
- [ ] Benchmark harness: DeepEval + RAGAS + SQLite results storage
- [ ] Phase 1 benchmarks: retrieval-only configs (vector vs hybrid vs rerank)
- [ ] HHEM hallucination detection (Vectara, <600MB, CPU)
- [ ] Claude Citations API integration (source attribution)
- [ ] Confidence gate: retry or "I don't know" for low-confidence answers

## v0.5 — Adaptive Architecture (Semantic Cache + Router)

- [ ] Semantic cache: FAISS (dev) → Redis+RediSearch (prod)
- [ ] Confidence-gated caching (only cache high-quality answers)
- [ ] Source-linked cache invalidation (re-indexed doc → invalidate cached answers)
- [ ] Query router: rule-based (<1ms) + Semantic Router (5-30ms) + LLM fallback
- [ ] LLM routing: Haiku for simple, Sonnet for complex (RouteLLM)
- [ ] CAG path: hot docs in Claude context + Anthropic prompt caching
- [ ] Phase 2 benchmarks: full pipeline with LLM (Faithfulness, Hallucination Rate)

## v0.6 — External Connectors + JIT Context

- [ ] Microsoft 365 Graph API connector (SharePoint, OneDrive, Education endpoints)
- [ ] OAuth2 flow for M365 (user-delegated + client credentials)
- [ ] Delta queries for incremental sync (only fetch changes)
- [ ] Webhooks for real-time change notifications (30-day renewal)
- [ ] Microsoft Teams bot (Bot Framework SDK, reuses M365 auth, adaptive cards for citations)
- [ ] JIT source fetch for "latest/recent" queries
- [ ] Phase 3 benchmarks: JIT freshness testing (change doc → query → verify)

## v0.7 — Agentic RAG + Multi-hop

- [ ] LangGraph state machine for complex query decomposition
- [ ] CRAG pattern: grade docs → rewrite query → retry loop
- [ ] Parallel sub-query retrieval for multi-hop questions
- [ ] Google Drive connector
- [ ] Slack bot with slash commands and conversational Q&A

## v0.8 — Deployment & Scaling

- [ ] Dockerfile for single-command deployment
- [ ] FastAPI web server (replaces Streamlit for production multi-user)
- [ ] SSE streaming for RAG responses (FastAPI 0.135.0+)
- [ ] Basic auth middleware (API key or Bearer token)
- [ ] Concurrent request handling (async search + LLM calls)
- [ ] Health checks (/health liveness + /ready readiness)

## v1.0 — Production Ready

- [ ] Comprehensive test suite (>80% coverage)
- [ ] SSO / OAuth integration (Keycloak or Auth0)
- [ ] ACL enforcement at retrieval layer (metadata filters)
- [ ] NeMo Guardrails for enterprise (topic containment, PII detection)
- [ ] Apple Silicon GPU acceleration (MPS backend)
- [ ] Multi-folder search (cross-collection queries)
- [ ] PyPI package publishing
- [ ] XLSX / email (.eml, .msg) parsing
