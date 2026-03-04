"""Hybrid search: BM25 + vector + RRF + optional cross-encoder reranking.

Pipeline:
  query → BM25 top N → ┐
                        ├→ RRF merge → top N → [reranker] → top K
  query → Vector top N → ┘
"""

from __future__ import annotations

import logging

from .config import BM25_CANDIDATE_MULTIPLIER, DEFAULT_TOP_K, ServerConfig
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


# ---------------------------------------------------------------------------
# Cross-encoder reranker (optional)
# ---------------------------------------------------------------------------

_reranker_model = None
_reranker_model_name: str | None = None
_reranker_disabled_for_session = False


def _get_reranker(model_name: str):
    """Lazy-load the cross-encoder model (cached for process lifetime)."""
    global _reranker_model, _reranker_model_name, _reranker_disabled_for_session
    if _reranker_disabled_for_session:
        return None

    if _reranker_model is None or _reranker_model_name != model_name:
        logger.info("Loading reranker model: %s", model_name)
        try:
            from sentence_transformers import CrossEncoder

            _reranker_model = CrossEncoder(model_name)
            _reranker_model_name = model_name
        except Exception:
            # EDGE-007-007: Download/load failure disables reranking for this session.
            logger.warning(
                "Reranker model download failed - reranking disabled for this session. "
                "Pre-download the model on a machine with internet access."
            )
            _reranker_disabled_for_session = True
            return None
    return _reranker_model


def _rerank(
    query: str,
    results: list[SearchResult],
    top_k: int,
    model_name: str,
) -> list[SearchResult]:
    """Rerank results using a cross-encoder model.

    Scores each (query, chunk_content) pair, re-sorts by score,
    and returns the top K.
    """
    # SPEC-007-001: Insert cross-encoder reranking after RRF when enabled.
    if not results:
        return results

    reranker = _get_reranker(model_name)
    if reranker is None:
        return results[:top_k]

    scored_results: list[SearchResult] = []
    tail_results: list[SearchResult] = []
    for result in results:
        if result.snippet.strip():
            scored_results.append(result)
        else:
            # EDGE-007-002: Empty chunk content is skipped and kept at tail.
            tail_results.append(result)

    if not scored_results:
        return results[:top_k]

    pairs = [(query, r.snippet) for r in scored_results]
    try:
        scores = reranker.predict(pairs)
    except Exception:
        logger.warning("Reranker inference failed - returning RRF ranking only")
        return results[:top_k]

    for result, score in zip(scored_results, scores):
        result.score = round(float(score), 6)

    reranked = sorted(scored_results, key=lambda r: r.score, reverse=True) + tail_results
    return reranked[:top_k]


# ---------------------------------------------------------------------------
# Main search function
# ---------------------------------------------------------------------------


def hybrid_search(
    store: ChunkStore,
    embedder: Embedder,
    query: str,
    top_k: int = DEFAULT_TOP_K,
    file_glob: str | None = None,
    config: ServerConfig | None = None,
) -> list[SearchResult]:
    """Run hybrid BM25 + vector search with RRF merging.

    Steps:
    1. Embed the query
    2. Run vector search (top candidates)
    3. Run BM25 search (top candidates)
    4. Merge with RRF
    5. (Optional) Rerank with cross-encoder
    6. Fetch metadata and build SearchResult objects
    """
    # SPEC-007-003: Candidate set sizing is configurable via reranker_top_n.
    reranker_enabled = config.reranker if config else False
    reranker_top_n = config.reranker_top_n if config else 20
    reranker_model = (
        config.reranker_model if config
        else "cross-encoder/ms-marco-MiniLM-L-6-v2"
    )

    candidate_count = top_k * BM25_CANDIDATE_MULTIPLIER

    # If reranker is on, fetch more candidates for RRF so the reranker
    # has a richer pool to re-sort.
    if reranker_enabled:
        rrf_top = max(reranker_top_n, top_k)
        candidate_count = max(candidate_count, rrf_top)
    else:
        rrf_top = top_k

    # 1. Embed query
    query_vector = embedder.embed_query(query)

    # 2. Vector search
    vec_ids = store.vector_search(
        query_vector, top_k=candidate_count, file_glob=file_glob,
    )
    logger.debug("Vector search returned %d candidates", len(vec_ids))

    # 3. BM25 search
    bm25_ids = store.bm25_search(
        query, top_k=candidate_count, file_glob=file_glob,
    )
    logger.debug("BM25 search returned %d candidates", len(bm25_ids))

    # 4. RRF merge
    if not vec_ids and not bm25_ids:
        return []

    merged = rrf_merge([vec_ids, bm25_ids])
    top_chunk_ids = [cid for cid, _ in merged[:rrf_top]]
    score_map = dict(merged[:rrf_top])

    # 5. Fetch metadata and build results
    metadatas = store.get_chunk_metadata(top_chunk_ids)

    results: list[SearchResult] = []
    for cid in top_chunk_ids:
        meta = metadatas.get(cid)
        if meta is None:
            continue
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

    # 6. Rerank (optional)
    if reranker_enabled and len(results) > 1:
        logger.debug(
            "Reranking %d results with %s", len(results), reranker_model,
        )
        results = _rerank(query, results, top_k, reranker_model)
    else:
        results = results[:top_k]

    return results
