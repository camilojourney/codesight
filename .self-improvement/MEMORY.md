# Self-Improvement Memory — codesight

## Project State

- **Version:** v0.3.0 (pluggable LLM + configurable embeddings + reranking)
- **Package:** `src/codesight/` — renamed from `semantic_search_mcp` in v0.2
- **Test coverage:** Minimal (placeholder tests only — needs real tests)
- **Last audit:** 2026-03-01

## Architecture Facts

- Run command: `python -m codesight <command>`
- Data dir: `~/.codesight/data/` (default, configurable via `CODESIGHT_DATA_DIR`)
- Python API: `from codesight import CodeSight`
- LLM backend: pluggable via `CODESIGHT_LLM_BACKEND` (claude/azure/openai/ollama)
- Embedding: configurable via `CODESIGHT_EMBEDDING_MODEL` + `CODESIGHT_EMBEDDING_BACKEND`
- Reranking: optional via `CODESIGHT_RERANKER=true`
- Search is 100% local, only `ask()` touches an LLM

## Key Source Files

| File | Purpose |
|------|---------|
| `api.py` | `CodeSight` class — single entry point |
| `llm.py` | Pluggable LLM backends (4 adapters) |
| `search.py` | Hybrid BM25 + vector + RRF + optional reranking |
| `embeddings.py` | Local or API embedding backends |
| `store.py` | LanceDB + SQLite FTS5 dual-write |
| `indexer.py` | File walking + chunking + embedding pipeline |
| `parsers.py` | PDF/DOCX/PPTX text extraction |
| `config.py` | All settings, model registry, env var defaults |

## Security Invariants (NEVER violate)

1. No writes to indexed folders — read-only
2. All resolved paths validated — no path traversal
3. No full file content in search results — chunks only
4. Content hash verified before re-embedding
5. Data dir isolated from indexed folder

## Known Issues

- Default embedding model still `all-MiniLM-L6-v2` (spec 002 targets upgrade to `nomic-embed-text-v1.5`)
- No real tests beyond placeholder imports
- Agent rule files in `.claude/agents/` reference old MCP architecture

## Implementation History

- v0.1: Hybrid BM25+vector code search (MCP server)
- v0.2: Enterprise document search pivot (package rename, parsers, Python API, Streamlit)
- v0.3: Pluggable LLM, configurable embeddings, cross-encoder reranking
