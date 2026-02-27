# Research — CodeSight

**Last updated:** 2026-02

---

## 1. Hybrid Retrieval Architecture

### Why Hybrid Matters
Pure vector search misses exact keyword matches (function names, error codes, literal strings). Pure BM25 misses semantic synonyms and conceptual relationships. Hybrid retrieval with Reciprocal Rank Fusion (RRF) combines both with zero extra infrastructure.

### Implementation
```
query string
    │
    ├──────────────────────────────────────────┐
    │                                          │
    ▼                                          ▼
SQLite FTS5                                LanceDB
BM25 keyword matching                  vector similarity
(exact function names,                 (semantic meaning,
 error codes, literals)                 concept proximity)
    │                                          │
    └──────────────┬───────────────────────────┘
                   ▼
          Reciprocal Rank Fusion
          score = Σ 1/(k + rank_i)  where k=60
                   │
                   ▼
            top K chunks
```

### RRF Parameters
- k=60 is the standard constant from the RRF paper (Cormack et al.)
- Changing k shifts recall/precision tradeoff — benchmark before modifying
- Each retriever contributes top 20 results before fusion

## 2. Chunking Strategy

### Language-Aware Regex Splitting
10 languages supported: Python, JS, TS, Go, Rust, Java, Ruby, PHP, C, C++. Splits on scope boundaries (class/function/block definitions) rather than fixed token counts.

Unknown languages fall back to sliding window with overlap.

### Context Headers
Each chunk gets a prepended context header before embedding:
```
# File: src/auth/jwt.py
# Scope: function validate_token
# Lines: 45-82
```

**Why:** The embedding model needs to know WHERE a chunk lives, not just what it says. Context headers improve retrieval relevance significantly.

### Deduplication
Content hash: `sha256(content)[:16]` per chunk. On re-index, unchanged chunks are skipped entirely — no re-embedding, no write. This makes incremental re-indexing fast.

## 3. Embedding Models

### Current Default
`all-MiniLM-L6-v2` (384 dims) — fast, no API key, good general performance.

### Better Options
| Model | Dims | Context | Notes |
|-------|------|---------|-------|
| all-MiniLM-L6-v2 | 384 | 256 | Default, fast, general-purpose |
| jina-embeddings-v2-base-code | 768 | 8192 | Code-specific, longer context |
| nomic-embed-text-v1.5 | 768 | 8192 | Long context, strong on code |
| voyage-code-3 | 1024 | 16384 | Best code embeddings (API-only) |

### MPS Acceleration
On Apple Silicon Macs, sentence-transformers automatically uses MPS (Metal Performance Shaders) for GPU-accelerated embedding. Embedding 10K chunks takes ~30s on M1.

### Model Mismatch Guard
If a repo was indexed with model A and the current model is B, the server detects the dimension mismatch and forces a full rebuild. This prevents silent search degradation.

## 4. Storage Architecture

### LanceDB (Vector Store)
- Serverless, file-based (no database process)
- Columnar storage optimized for vector operations
- Fast ANN (approximate nearest neighbor) search
- Stores: chunk_id, embedding vector, metadata (file_path, lines, scope)

### SQLite FTS5 (Keyword Index)
- Built into Python's sqlite3 module (no extra dependency)
- Full-text search virtual table with BM25 ranking
- Auto-synced via database triggers on insert/update/delete
- Stores: chunk_id, content, file_path, line range

### Storage Layout
```
~/.semantic-search/data/
└── <sha256(repo_path)[:16]>/
    ├── lancedb/          ← vector tables
    │   └── chunks.lance
    └── fts.db            ← SQLite FTS5
```

All indexes live outside the indexed repo — never write inside user's codebase.

## 5. MCP Protocol Integration

### FastMCP Framework
Built on `fastmcp` — lightweight MCP server framework for Python. Registers 3 tools:

```python
search(query, repo_path?, top_k?, file_glob?) → list[SearchResult]
index(repo_path?, force_rebuild?) → IndexStatus
status(repo_path?) → IndexStatus
```

### Tool Contract
Tool signatures are the public API contract. Claude Code caches tool definitions — a signature change breaks active sessions. Never change without version bump.

### Planned Tools (v0.3)
```python
watch(repo_path?) → None   # Register repo for automatic refresh
unwatch(repo_path?) → None # Unregister
```

## 6. .gitignore-Aware File Walking

Uses `pathspec` library to parse `.gitignore` patterns. Only indexes files that would be tracked by git:
- Respects nested `.gitignore` files
- Excludes `node_modules/`, `.git/`, build artifacts by default
- Supports custom exclusion patterns via config

## 7. Performance Characteristics

### Indexing Speed
| Repo Size | Files | Chunks | Index Time (M1) |
|-----------|-------|--------|------------------|
| Small (1K files) | ~1,000 | ~5,000 | ~10s |
| Medium (10K files) | ~10,000 | ~50,000 | ~2 min |
| Large (100K files) | ~100,000 | ~500,000 | ~20 min |

### Search Latency
- Vector search: ~5ms (LanceDB ANN)
- BM25 search: ~2ms (SQLite FTS5)
- RRF merge: ~1ms
- **Total: <10ms** per query (after index is loaded)

### Freshness
- `SEMANTIC_SEARCH_STALE_MINUTES=60` — index is considered stale after 1 hour
- `status()` tool reports staleness to the AI assistant
- Incremental re-index only processes changed files (content hash comparison)

## 8. Key Technical Decisions

| Decision | Choice | Why |
|----------|--------|-----|
| Vector DB | LanceDB | Serverless, no process, file-based |
| Keyword search | SQLite FTS5 | Built into Python, no dependency |
| Fusion | RRF (k=60) | Simple, effective, no tuning needed |
| Chunking | Language-aware regex | Preserves code scope boundaries |
| Embedding | all-MiniLM-L6-v2 | No API key, fast, configurable |
| MCP framework | FastMCP | Lightweight, Python-native |
| File walking | pathspec (.gitignore) | Respects developer expectations |

## 9. Research Directions

1. **Code-specific embeddings** — Switch to `jina-embeddings-v2-base-code` or `voyage-code-3` for better code retrieval
2. **Cross-repo search** — Index multiple repos and search across them with scope filtering
3. **Watch mode** — File system watcher for real-time index updates
4. **Reranking** — Add a cross-encoder reranker after RRF for improved precision on top results
5. **Graph-enhanced retrieval** — Use AST parsing to build call graphs, include related functions in results
