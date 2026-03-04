from __future__ import annotations

import importlib
import sys
from pathlib import Path
from types import ModuleType

import pytest

from codesight.api import CodeSight
from codesight.config import ServerConfig
from codesight.embeddings import APIEmbedder, LocalEmbedder, get_embedder


def test_spec_002_001_default_model_upgrade(monkeypatch: pytest.MonkeyPatch):
    """SPEC-002-001: Default model is nomic-embed-text-v1.5 with 768 dimensions."""
    monkeypatch.delenv("CODESIGHT_EMBEDDING_MODEL", raising=False)
    monkeypatch.delenv("CODESIGHT_EMBEDDING_BACKEND", raising=False)

    import codesight.config as config

    reloaded = importlib.reload(config)
    assert reloaded.DEFAULT_EMBEDDING_MODEL == "nomic-embed-text-v1.5"
    assert reloaded.DEFAULT_EMBEDDING_DIM == 768


def test_spec_002_002_allowlist_validation_rejects_unknown_model():
    """SPEC-002-002: Invalid model names fail fast with valid options."""
    get_embedder.cache_clear()
    with pytest.raises(ValueError, match="Valid options:"):
        get_embedder(model_name="not-a-real-model", backend="local")


def test_spec_002_003_dimension_mismatch_detection(tmp_path: Path):
    """SPEC-002-003: Stored embedding dimensions mismatch triggers rebuild check."""

    class _FTS:
        def __init__(self):
            self.meta = {
                "embedding_model": "nomic-embed-text-v1.5",
                "embedding_dim": "384",
            }

        def get_meta(self, key: str):
            return self.meta.get(key)

    class _Store:
        def __init__(self):
            self.fts = _FTS()

    engine = CodeSight(
        tmp_path,
        config=ServerConfig(
            embedding_model="nomic-embed-text-v1.5",
            embedding_backend="local",
        ),
    )
    engine._store = _Store()
    assert engine._embedding_model_changed() is True


def test_spec_002_004_api_backend_requires_openai_key(monkeypatch: pytest.MonkeyPatch):
    """SPEC-002-004: API backend names OPENAI_API_KEY before any network call."""
    get_embedder.cache_clear()
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        get_embedder(model_name="text-embedding-3-large", backend="api")


def test_spec_002_004_api_batch_splitting_uses_512(monkeypatch: pytest.MonkeyPatch):
    """SPEC-002-004: API embedding batches inputs into groups of 512."""
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    embedder = APIEmbedder(model_name="text-embedding-3-large", expected_dim=3)

    class _Item:
        def __init__(self):
            self.embedding = [1.0, 0.0, 0.0]

    class _Embeddings:
        def __init__(self):
            self.calls: list[int] = []

        def create(self, *, model: str, input: list[str]):
            self.calls.append(len(input))
            assert model == "text-embedding-3-large"
            return type("Response", (), {"data": [_Item() for _ in input]})()

    class _Client:
        def __init__(self):
            self.embeddings = _Embeddings()

    client = _Client()
    embedder._client = client
    vectors = embedder.embed(["hello"] * 1025)
    assert vectors.shape == (1025, 3)
    assert client.embeddings.calls == [512, 512, 1]


def test_edge_002_001_missing_local_model_has_clear_error(monkeypatch: pytest.MonkeyPatch):
    """EDGE-002-001: Missing local model error includes installation guidance."""
    module = ModuleType("sentence_transformers")

    class _BrokenSentenceTransformer:
        def __init__(self, *_args, **_kwargs):
            raise RuntimeError("model download failed")

    module.SentenceTransformer = _BrokenSentenceTransformer
    monkeypatch.setitem(sys.modules, "sentence_transformers", module)

    embedder = LocalEmbedder(model_name="nomic-embed-text-v1.5", expected_dim=768)
    with pytest.raises(ValueError, match="Model 'nomic-embed-text-v1.5' not found locally"):
        _ = embedder.model


def test_edge_002_002_api_unreachable_suggests_local(monkeypatch: pytest.MonkeyPatch):
    """EDGE-002-002: API network failures suggest local backend fallback."""
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    embedder = APIEmbedder(model_name="text-embedding-3-large", expected_dim=3)

    class _BrokenEmbeddings:
        def create(self, *, model: str, input: list[str]):
            raise RuntimeError("connection timed out")

    class _Client:
        def __init__(self):
            self.embeddings = _BrokenEmbeddings()

    embedder._client = _Client()
    with pytest.raises(ConnectionError, match="CODESIGHT_EMBEDDING_BACKEND=local"):
        embedder.embed(["hello"])


def test_edge_002_003_api_rate_limit_after_retries(monkeypatch: pytest.MonkeyPatch):
    """EDGE-002-003: API 429 retries use exponential backoff and then fail."""
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr("codesight.embeddings.time.sleep", lambda _seconds: None)
    embedder = APIEmbedder(model_name="text-embedding-3-large", expected_dim=3)
    calls = {"count": 0}

    class _RateLimitError(RuntimeError):
        status_code = 429

    class _RateLimitedEmbeddings:
        def create(self, *, model: str, input: list[str]):
            calls["count"] += 1
            raise _RateLimitError("429 rate limited")

    class _Client:
        def __init__(self):
            self.embeddings = _RateLimitedEmbeddings()

    embedder._client = _Client()
    with pytest.raises(RuntimeError, match="rate limited after 3 retries"):
        embedder.embed(["hello"])
    assert calls["count"] == 4
