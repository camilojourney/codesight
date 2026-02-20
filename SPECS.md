# Architecture & Specs

## Design Decisions

### 1. LanceDB — Vector Store

| Criteria | LanceDB | ChromaDB | FAISS |
|---|---|---|---|
| Embedded (no server) | ✅ | ✅ | ✅ |
| Metadata filtering | ✅ | ✅ | ❌ (manual) |
| Write stability | ✅ (proven) | ⚠️ HNSW corruption issues | ✅ |
| Disk persistence | ✅ Apache Arrow | ✅ SQLite/DuckDB | Manual |
| Scalability (local) | Millions | Millions | Billions |

- [`mcp-vector-search`](https://github.com/bobmatnyc/mcp-vector-search) migrated away from ChromaDB to LanceDB for stability — validates this choice
- FAISS is faster at raw search but requires manual everything — overkill for a local MCP tool
- LanceDB's embedded, file-based design is the right fit for single-user local use

### 2. Hybrid BM25 + Vector + RRF Retrieval

**Key differentiator — no competitor does this.**

- Pure vector search misses exact keyword matches (function names, error codes, variable names)
- Our RRF approach combines BM25 (via SQLite FTS5) and vector search with zero additional infra
- This is a real advantage over `mcp-vector-search` which does vector-only

```
Query → ┬→ BM25 (FTS5)    → top 20 candidates ─┐
        │                                        ├─ RRF merge → top K
        └→ Vector (LanceDB) → top 20 candidates ─┘
```

### 3. STDIO Transport

- Standard transport for local MCP servers launched by Claude Code
- Claude Code spawns the process and communicates via JSON-RPC over stdin/stdout
- Streamable HTTP is the production pattern for multi-user/remote — not needed here

### 4. SQLite FTS5 Sidecar for BM25

- FTS5 is built into Python's `sqlite3` — no extra install
- Triggers keep FTS index in sync automatically
- Co-located with metadata for fast chunk lookups

### 5. `.gitignore`-Aware File Walking

- Avoids indexing `node_modules/`, `.git/`, `dist/`, `__pycache__/`, etc.
- `pathspec` library handles `.gitignore` glob patterns correctly
- Hardcoded skip lists catch patterns `.gitignore` might miss

### 6. Language-Aware Regex Chunking (Phase 1)

Scope-delimited splitting for 10 languages (Python, JS, TS, Go, Rust, Java, Ruby, PHP, C, C++), with overlapping window fallback for unknown languages.

Each chunk gets a context header prepended before embedding:
```
# File: src/auth/jwt.py
# Scope: function validate_token
# Lines: 45-82
```

### 7. Content Hashing for Incremental Indexing

- `sha256(chunk_content)[:16]` per chunk
- Skip re-embedding if hash unchanged
- Avoids wasting compute on unchanged functions in modified files

---

## Competitive Landscape

| Project | Approach | Hybrid Search | Our Edge |
|---|---|---|---|
| [`mcp-vector-search`](https://github.com/bobmatnyc/mcp-vector-search) | AST + LanceDB embeddings | ❌ Vector only | ✅ BM25 + vector + RRF |
| [`serena`](https://github.com/oraios/serena) | LSP symbol-level retrieval | N/A (structural) | Different paradigm — complementary |
| `mcp-codebase-index` | Structural metadata, 17 tools | ❌ | Simpler tool surface, semantic understanding |
