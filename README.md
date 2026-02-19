# Semantic Search MCP Server

Semantic code search for Claude Code — powered by hybrid BM25 + vector retrieval.

## What It Does

An MCP server that gives Claude Code semantic search over your codebase. Unlike pure vector search, this uses **hybrid retrieval** (BM25 keyword matching + vector semantic search + Reciprocal Rank Fusion) for significantly better results.

## Quick Start

```bash
# Install
cd semantic_search_MCP
pip install -e ".[dev]"

# Test the server with MCP inspector
npx @modelcontextprotocol/inspector python -m semantic_search_mcp

# Connect to Claude Code
claude mcp add semantic-search -- python -m semantic_search_mcp
```

## Tools

| Tool | Description |
|---|---|
| `search(query, repo_path?, top_k?, file_glob?)` | Hybrid semantic + keyword search. Auto-indexes if needed. |
| `index(repo_path?, force_rebuild?)` | Build or rebuild the search index. |
| `status(repo_path?)` | Check if a repo is indexed and whether the index is stale. |

## Example Usage (inside Claude Code)

```
> Search for where JWT validation happens
> Index this repository first, then find auth middleware
> Search for error handling in src/api/**
```

## Architecture

- **Chunking**: Language-aware regex splitting (10 languages) with context headers
- **Embeddings**: `all-MiniLM-L6-v2` via sentence-transformers (local, no API key)
- **Vector store**: LanceDB (serverless, file-based)
- **BM25**: SQLite FTS5 sidecar
- **Retrieval**: Hybrid BM25 + vector with RRF merge

## Stack

- Python 3.11+
- FastMCP (MCP server framework)
- LanceDB (vector storage)
- sentence-transformers (embeddings)
- SQLite FTS5 (keyword search)

## Configuration

Set via environment variables:

| Variable | Default | Description |
|---|---|---|
| `SEMANTIC_SEARCH_DATA_DIR` | `~/.semantic-search/data` | Where indexes are stored |
