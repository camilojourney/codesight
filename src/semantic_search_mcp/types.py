"""Pydantic models for tool inputs and outputs."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ChunkRecord(BaseModel):
    """A single code chunk stored in the index."""

    chunk_id: str
    repo_path: str
    file_path: str  # relative to repo root
    start_line: int
    end_line: int
    scope: str  # e.g. "class Foo > method bar"
    content: str
    content_hash: str
    language: str


class SearchResult(BaseModel):
    """A single search result returned to Claude."""

    file_path: str
    start_line: int
    end_line: int
    snippet: str
    score: float
    scope: str
    chunk_id: str


class IndexStats(BaseModel):
    """Summary returned after indexing a repo."""

    repo_path: str
    files_indexed: int
    chunks_created: int
    chunks_skipped_unchanged: int = 0
    chunks_deleted: int = 0
    total_chunks: int
    elapsed_seconds: float


class RepoStatus(BaseModel):
    """Status info for an indexed repo."""

    repo_path: str
    indexed: bool
    chunk_count: int = 0
    files_indexed: int = 0
    last_commit: str | None = None
    last_indexed_at: str | None = None
    stale: bool = False
