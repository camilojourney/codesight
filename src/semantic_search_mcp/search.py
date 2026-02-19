"""Hybrid search: BM25 + vector + Reciprocal Rank Fusion (RRF).

This is our key differentiator — no existing MCP code search tool
combines BM25 keyword matching with vector semantic search.
"""

from __future__ import annotations

import logging

import numpy as np

from .config import BM25_CANDIDATE_MULTIPLIER, DEFAULT_TOP_K
from .embeddings import Embedder
from .store import ChunkStore
from .types import SearchResult

logger = logging.getLogger(__name__)


def rrf_merge(
    ranked_lists: list[list[str]],
    k: int = 60,
) -> list[tuple[str, float]]:
    """Reciprocal Rank Fusion across multiple ranked ID lists.

    Returns [(chunk_id, rrf_score)] sorted by score descending.
    The constant k controls how much we penalize low-ranked items.
    k=60 is the standard value from the original RRF paper.
    """
    scores: dict[str, float] = {}
    for ranked in ranked_lists:
        for rank, doc_id in enumerate(ranked):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank + 1)
    return sorted(scores.items(), key=lambda x: x[1], reverse=True)


def hybrid_search(
    store: ChunkStore,
    embedder: Embedder,
    query: str,
    top_k: int = DEFAULT_TOP_K,
    file_glob: str | None = None,
) -> list[SearchResult]:
    """Run hybrid BM25 + vector search with RRF merging.

    Steps:
    1. Embed the query
    2. Run vector search (top candidates)
    3. Run BM25 search (top candidates)
    4. Merge with RRF
    5. Fetch metadata and build SearchResult objects
    """
    candidate_count = top_k * BM25_CANDIDATE_MULTIPLIER

    # 1. Embed query
    query_vector = embedder.embed_query(query)

    # 2. Vector search
    vec_ids = store.vector_search(query_vector, top_k=candidate_count, file_glob=file_glob)
    logger.debug("Vector search returned %d candidates", len(vec_ids))

    # 3. BM25 search
    bm25_ids = store.bm25_search(query, top_k=candidate_count, file_glob=file_glob)
    logger.debug("BM25 search returned %d candidates", len(bm25_ids))

    # 4. RRF merge
    if not vec_ids and not bm25_ids:
        return []

    merged = rrf_merge([vec_ids, bm25_ids])
    top_chunk_ids = [cid for cid, _ in merged[:top_k]]
    score_map = dict(merged[:top_k])

    # 5. Fetch metadata and build results
    metadatas = store.get_chunk_metadata(top_chunk_ids)

    results: list[SearchResult] = []
    for cid in top_chunk_ids:
        meta = metadatas.get(cid)
        if meta is None:
            continue
        # Truncate snippet to avoid dumping huge chunks
        snippet = meta["content"]
        if len(snippet) > 1500:
            snippet = snippet[:1500] + "\n... (truncated)"

        results.append(SearchResult(
            file_path=meta["file_path"],
            start_line=meta["start_line"],
            end_line=meta["end_line"],
            snippet=snippet,
            score=round(score_map.get(cid, 0.0), 6),
            scope=meta["scope"],
            chunk_id=cid,
        ))

    return results
