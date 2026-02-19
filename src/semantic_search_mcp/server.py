"""FastMCP server — exposes search, index, and status tools over STDIO.

This is what Claude Code connects to via JSON-RPC.
Run with: python -m semantic_search_mcp.server
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from fastmcp import FastMCP

from .config import ServerConfig, STALE_THRESHOLD_SECONDS
from .embeddings import get_embedder
from .indexer import index_repo
from .search import hybrid_search
from .store import ChunkStore
from .types import IndexStats, RepoStatus, SearchResult

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Server setup
# ---------------------------------------------------------------------------

mcp = FastMCP(
    name="semantic-search",
    version="0.1.0",
    description="Semantic code search for your repositories. "
    "Index and search codebases using hybrid BM25 + vector retrieval.",
)

config = ServerConfig()


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _resolve_repo(repo_path: str | None) -> Path:
    """Resolve repo path, defaulting to CWD."""
    if repo_path:
        p = Path(repo_path).expanduser().resolve()
    else:
        p = Path.cwd().resolve()
    if not p.is_dir():
        raise ValueError(f"Not a directory: {p}")
    return p


def _is_stale(store: ChunkStore) -> bool:
    """Check if the index is stale (older than threshold)."""
    ts = store.last_indexed_at
    if not ts:
        return True
    from datetime import datetime, timezone
    try:
        indexed_at = datetime.fromisoformat(ts)
        age = (datetime.now(timezone.utc) - indexed_at).total_seconds()
        return age > config.stale_threshold_seconds
    except Exception:
        return True


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@mcp.tool()
def search(
    query: str,
    repo_path: str | None = None,
    top_k: int = 8,
    file_glob: str | None = None,
) -> list[dict]:
    """Search the codebase semantically.

    Uses hybrid BM25 + vector retrieval for best results.
    Auto-indexes if no index exists. Auto-refreshes if the index is stale.

    Args:
        query: Natural language search query (e.g. "JWT validation logic")
        repo_path: Path to the repository. Defaults to current working directory.
        top_k: Number of results to return (default: 8)
        file_glob: Optional glob pattern to filter files (e.g. "src/auth/**")

    Returns:
        List of search results with file_path, start_line, end_line, snippet,
        score, and scope information.
    """
    repo = _resolve_repo(repo_path)
    store = ChunkStore(repo, embedding_dim=config.embedding_dim)

    # Auto-index if not indexed
    if not store.is_indexed:
        logger.info("No index found for %s — building now...", repo)
        index_repo(repo, config)
        # Re-open store to pick up new data
        store = ChunkStore(repo, embedding_dim=config.embedding_dim)

    # Auto-refresh if stale
    elif _is_stale(store):
        logger.info("Index is stale for %s — refreshing...", repo)
        index_repo(repo, config)
        store = ChunkStore(repo, embedding_dim=config.embedding_dim)

    embedder = get_embedder(config.embedding_model, config.embedding_dim)
    results = hybrid_search(store, embedder, query, top_k=top_k, file_glob=file_glob)

    return [r.model_dump() for r in results]


@mcp.tool()
def index(
    repo_path: str | None = None,
    force_rebuild: bool = False,
) -> dict:
    """Index a repository for semantic search.

    Walks all files, chunks them intelligently, embeds with sentence-transformers,
    and stores in a local vector database. Unchanged chunks are skipped.

    Args:
        repo_path: Path to the repository. Defaults to current working directory.
        force_rebuild: If True, rebuild the entire index from scratch.

    Returns:
        Statistics about the indexing operation.
    """
    repo = _resolve_repo(repo_path)
    stats = index_repo(repo, config, force_rebuild=force_rebuild)
    return stats.model_dump()


@mcp.tool()
def status(
    repo_path: str | None = None,
) -> dict:
    """Check the index status of a repository.

    Args:
        repo_path: Path to the repository. Defaults to current working directory.

    Returns:
        Status information including whether the repo is indexed, chunk count,
        last commit, and whether the index is stale.
    """
    repo = _resolve_repo(repo_path)
    store = ChunkStore(repo, embedding_dim=config.embedding_dim)

    repo_status = RepoStatus(
        repo_path=str(repo),
        indexed=store.is_indexed,
        chunk_count=store.chunk_count,
        files_indexed=store.file_count,
        last_commit=store.last_commit,
        last_indexed_at=store.last_indexed_at,
        stale=_is_stale(store) if store.is_indexed else False,
    )

    return repo_status.model_dump()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main():
    """Run the MCP server over STDIO."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
