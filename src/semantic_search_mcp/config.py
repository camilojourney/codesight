"""Configuration for the semantic search MCP server."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

DATA_DIR = Path(
    os.environ.get("SEMANTIC_SEARCH_DATA_DIR", Path.home() / ".semantic-search" / "data")
)


def repo_data_dir(repo_path: str | Path) -> Path:
    """Return the data directory for a given repo, creating parent dirs if needed.

    Each repo gets its own subdirectory containing:
      - LanceDB table files (vectors)
      - metadata.db (SQLite FTS5 sidecar for BM25)
    """
    canonical = os.path.realpath(str(repo_path))
    short_hash = hashlib.sha256(canonical.encode()).hexdigest()[:12]
    data_dir = DATA_DIR / short_hash
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def repo_fts_db_path(repo_path: str | Path) -> Path:
    """Return the SQLite FTS5 sidecar DB path for a given repo."""
    return repo_data_dir(repo_path) / "metadata.db"


# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

DEFAULT_EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
DEFAULT_EMBEDDING_DIM = 384
DEFAULT_TOP_K = 8
DEFAULT_CHUNK_MAX_LINES = 200
DEFAULT_CHUNK_OVERLAP_LINES = 50
STALE_THRESHOLD_SECONDS = 300  # 5 minutes
BM25_CANDIDATE_MULTIPLIER = 3  # fetch 3x top_k from each retriever before RRF


# ---------------------------------------------------------------------------
# File walking
# ---------------------------------------------------------------------------

INDEXABLE_EXTENSIONS: set[str] = {
    ".py", ".js", ".ts", ".tsx", ".jsx",
    ".go", ".rs", ".java", ".kt", ".scala",
    ".c", ".cpp", ".h", ".hpp", ".cs",
    ".rb", ".php", ".swift", ".m",
    ".sql", ".sh", ".bash", ".zsh",
    ".yaml", ".yml", ".toml", ".json",
    ".md", ".txt", ".rst",
    ".html", ".css", ".scss",
    ".tf", ".hcl",
    ".proto", ".graphql",
    ".lua", ".r", ".jl",
    ".ex", ".exs", ".erl",
    ".zig", ".nim", ".v",
    ".dockerfile",
}

ALWAYS_SKIP_DIRS: set[str] = {
    ".git", "__pycache__", "node_modules", ".venv", "venv",
    ".tox", ".mypy_cache", ".pytest_cache", ".ruff_cache",
    "dist", "build", ".eggs", ".next", ".nuxt",
    "vendor", "target", "Pods",
}

ALWAYS_SKIP_FILES: set[str] = {
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
    "poetry.lock", "Cargo.lock", "Gemfile.lock",
    "go.sum", "composer.lock",
}

MAX_FILE_SIZE_BYTES = 1_000_000  # 1 MB


class ServerConfig(BaseModel):
    """Runtime configuration."""

    embedding_model: str = Field(default=DEFAULT_EMBEDDING_MODEL)
    embedding_dim: int = Field(default=DEFAULT_EMBEDDING_DIM)
    top_k: int = Field(default=DEFAULT_TOP_K)
    chunk_max_lines: int = Field(default=DEFAULT_CHUNK_MAX_LINES)
    chunk_overlap_lines: int = Field(default=DEFAULT_CHUNK_OVERLAP_LINES)
    stale_threshold_seconds: int = Field(default=STALE_THRESHOLD_SECONDS)
