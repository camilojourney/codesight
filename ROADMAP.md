# Roadmap

## v0.1 — Current ✅
- [x] FastMCP server with 3 tools (`search`, `index`, `status`)
- [x] Hybrid BM25 + vector retrieval with RRF merge
- [x] LanceDB vectors + SQLite FTS5 sidecar
- [x] Language-aware regex chunking (10 languages)
- [x] `all-MiniLM-L6-v2` local embeddings (no API key)
- [x] `.gitignore`-aware file walking
- [x] Content hashing (skip unchanged chunks)
- [x] Auto-index on first search, auto-refresh when stale

## v0.2 — Embedding Quality 🔮
- [ ] Add `nomic-embed-text-v1.5` as config option (768 dims, 8K context, handles code + NL)
- [ ] Add `jina-embeddings-v2-base-code` as config option (code-specific)
- [ ] File preamble in chunk context (imports/docstrings prepended to embedding text)
- [ ] Configurable embedding model via environment variable

## v0.3 — Incremental Refresh 🔮
- [ ] Git-diff based incremental indexing (`git diff --name-only`)
- [ ] Only re-embed changed files on refresh
- [ ] Delete vectors for removed files
- [ ] Search-triggered staleness check with configurable threshold

## v0.4 — Tree-sitter Chunking 🔮
- [ ] Replace regex chunking with tree-sitter AST parsing
- [ ] Hierarchical chunking (class → method → block)
- [ ] Cross-language support from one parser library
- [ ] Exact AST node boundaries (no regex edge cases)

## v1.0 — Production Ready 🔮
- [ ] Comprehensive test suite
- [ ] Apple Silicon GPU acceleration (MPS backend)
- [ ] Batch embedding optimization
- [ ] Streamable HTTP transport option (for remote/multi-user)
- [ ] PyPI package publishing
- [ ] MCP marketplace listing
