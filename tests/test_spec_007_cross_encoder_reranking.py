from __future__ import annotations

import sys
from types import ModuleType

import numpy as np
import pytest

from codesight import search as search_module
from codesight.config import ServerConfig
from codesight.search import _get_reranker, _rerank, hybrid_search
from codesight.types import SearchResult


class _StubEmbedder:
    def embed_query(self, _query: str) -> np.ndarray:
        return np.array([0.1, 0.2], dtype=np.float32)


class _StubStore:
    def __init__(self) -> None:
        self.vec_top_k: int | None = None
        self.bm25_top_k: int | None = None
        self._ids = [f"chunk-{i}" for i in range(1, 31)]
        self._meta = {
            cid: {
                "file_path": f"file_{idx}.py",
                "start_line": 1,
                "end_line": 2,
                "content": f"snippet {idx}",
                "scope": f"function f{idx}",
            }
            for idx, cid in enumerate(self._ids, start=1)
        }

    def vector_search(self, _query_vector, top_k: int = 20, file_glob: str | None = None):
        self.vec_top_k = top_k
        return self._ids[:top_k]

    def bm25_search(self, _query: str, top_k: int = 20, file_glob: str | None = None):
        self.bm25_top_k = top_k
        return list(reversed(self._ids[:top_k]))

    def get_chunk_metadata(self, chunk_ids: list[str]):
        return {cid: self._meta[cid] for cid in chunk_ids}


def _mk_result(chunk_id: str, snippet: str, score: float) -> SearchResult:
    return SearchResult(
        file_path="file.py",
        start_line=1,
        end_line=2,
        snippet=snippet,
        score=score,
        scope="function x",
        chunk_id=chunk_id,
    )


def test_spec_007_001_reranker_disabled_has_no_overhead(monkeypatch: pytest.MonkeyPatch):
    """SPEC-007-001: Disabled reranker path does not invoke reranker code."""
    store = _StubStore()
    embedder = _StubEmbedder()

    monkeypatch.setattr(
        search_module,
        "_rerank",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("should not rerank")),
    )
    config = ServerConfig(reranker=False)
    results = hybrid_search(store, embedder, "query", top_k=5, config=config)
    assert len(results) == 5


def test_spec_007_003_candidate_set_uses_reranker_top_n(monkeypatch: pytest.MonkeyPatch):
    """SPEC-007-003: RRF candidate count expands to reranker_top_n when enabled."""
    store = _StubStore()
    embedder = _StubEmbedder()
    monkeypatch.setattr(search_module, "_rerank", lambda _q, results, top_k, _m: results[:top_k])

    config = ServerConfig(reranker=True, reranker_top_n=20)
    _ = hybrid_search(store, embedder, "query", top_k=5, config=config)
    assert store.vec_top_k == 20
    assert store.bm25_top_k == 20


def test_spec_007_004_rerank_reorders_by_cross_encoder_score(monkeypatch: pytest.MonkeyPatch):
    """SPEC-007-004: Reranker replaces RRF ordering with cross-encoder scores."""
    results = [
        _mk_result("a", "first", 0.1),
        _mk_result("b", "second", 0.1),
    ]

    class _FakeReranker:
        def predict(self, _pairs):
            return [0.1, 0.9]

    monkeypatch.setattr(search_module, "_get_reranker", lambda _name: _FakeReranker())
    reranked = _rerank("query", results, top_k=2, model_name="dummy")
    assert [item.chunk_id for item in reranked] == ["b", "a"]


def test_edge_007_002_empty_snippets_are_kept_at_tail(monkeypatch: pytest.MonkeyPatch):
    """EDGE-007-002: Empty snippets are skipped by reranker and kept at tail."""
    results = [
        _mk_result("empty", "   ", 0.7),
        _mk_result("filled", "real snippet", 0.6),
    ]

    class _FakeReranker:
        def predict(self, _pairs):
            return [0.95]

    monkeypatch.setattr(search_module, "_get_reranker", lambda _name: _FakeReranker())
    reranked = _rerank("query", results, top_k=2, model_name="dummy")
    assert [item.chunk_id for item in reranked] == ["filled", "empty"]


def test_edge_007_007_model_load_failure_disables_session(monkeypatch: pytest.MonkeyPatch):
    """EDGE-007-007: Model load failure disables reranking for the process session."""
    module = ModuleType("sentence_transformers")

    class _BrokenCrossEncoder:
        def __init__(self, *_args, **_kwargs):
            raise RuntimeError("offline")

    module.CrossEncoder = _BrokenCrossEncoder
    monkeypatch.setitem(sys.modules, "sentence_transformers", module)
    monkeypatch.setattr(search_module, "_reranker_model", None)
    monkeypatch.setattr(search_module, "_reranker_model_name", None)
    monkeypatch.setattr(search_module, "_reranker_disabled_for_session", False)

    assert _get_reranker("cross-encoder/ms-marco-MiniLM-L-6-v2") is None
    assert search_module._reranker_disabled_for_session is True
