# codesight

AI-powered document search engine — hybrid BM25 + vector + RRF retrieval with Claude answer synthesis.

## Quick Start

```bash
# Install
pip install -e ".[dev]"

# Index a folder of documents
python -m codesight index /path/to/documents

# Search
python -m codesight search "payment terms" /path/to/documents

# Ask a question (requires ANTHROPIC_API_KEY)
python -m codesight ask "What are the payment terms?" /path/to/documents

# Launch the web chat UI
pip install -e ".[demo]"
python -m codesight demo
```

## Python API

```python
from codesight import CodeSight

engine = CodeSight("/path/to/documents")
engine.index()                                     # Index all files
results = engine.search("payment terms")           # Hybrid search
answer = engine.ask("What are the payment terms?") # Search + Claude answer
status = engine.status()                           # Index freshness check
```

## Supported Formats

| Format | Extension | Parser |
|--------|-----------|--------|
| PDF | `.pdf` | pymupdf |
| Word | `.docx` | python-docx |
| PowerPoint | `.pptx` | python-pptx |
| Code | `.py`, `.js`, `.ts`, `.go`, `.rs`, etc. | Built-in (10 languages) |
| Text | `.md`, `.txt`, `.csv` | Built-in |

## Architecture

- **Document Parsing**: PDF, DOCX, PPTX text extraction with page/section metadata
- **Chunking**: Language-aware regex splitting (code) + paragraph-aware splitting (documents)
- **Embeddings**: `all-MiniLM-L6-v2` via sentence-transformers (local, no API key)
- **Vector Store**: LanceDB (serverless, file-based)
- **Keyword Search**: SQLite FTS5 sidecar
- **Retrieval**: Hybrid BM25 + vector with RRF merge
- **Answer Synthesis**: Claude API generates answers with source citations

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full system tour.

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | — | Required for `ask()` / Claude answer synthesis |
| `CODESIGHT_DATA_DIR` | `~/.codesight/data` | Where indexes are stored |
| `CODESIGHT_EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | Embedding model |
| `CODESIGHT_LLM_MODEL` | `claude-sonnet-4-20250514` | Claude model for answers |
| `CODESIGHT_STALE_MINUTES` | `60` | Index freshness threshold |
| `LOG_LEVEL` | `INFO` | Logging verbosity |

See [.env.example](.env.example) for all options.


## Workflow: Explore → Plan → Execute → Review

Opus in VS Code plans and launches autonomous CLI agents in the background — the user never leaves the conversation. Agents run via `env -u CLAUDECODE claude --dangerously-skip-permissions --model [model] -p '...'` with output redirected to files. Multiple cycles ensure quality: Sonnet implements, Opus reviews. See `.claude/rules/workflow.md` for full details.

## Stack

- Python 3.11+
- LanceDB + SQLite FTS5
- sentence-transformers
- Anthropic Claude API
- Streamlit (web chat UI)
- pymupdf, python-docx, python-pptx (document parsing)
