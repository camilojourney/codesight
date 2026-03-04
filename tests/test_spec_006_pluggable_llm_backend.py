from __future__ import annotations

from pathlib import Path

import pytest

import codesight.api as api_module
from codesight.api import CodeSight
from codesight.config import ServerConfig
from codesight.llm import (
    LLMResponse,
    _run_cloud_call_with_retry,
    get_backend,
)
from codesight.types import SearchResult


def _mk_result() -> SearchResult:
    return SearchResult(
        file_path="src/codesight/api.py",
        start_line=10,
        end_line=14,
        snippet="sample snippet",
        score=1.0,
        scope="function ask",
        chunk_id="chunk-1",
    )


def test_spec_006_001_backend_selection(monkeypatch: pytest.MonkeyPatch):
    """SPEC-006-001: Backend factory supports claude/azure/openai/ollama."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.openai.azure.com/")
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "x")
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")
    monkeypatch.setenv("OPENAI_API_KEY", "x")

    assert get_backend("claude").model_id.startswith("claude:")
    assert get_backend("azure").model_id.startswith("azure:")
    assert get_backend("openai").model_id.startswith("openai:")
    assert get_backend("ollama").model_id.startswith("ollama:")

    with pytest.raises(ValueError, match="Valid options"):
        get_backend("invalid-backend")


def test_spec_006_002_search_remains_local_without_llm(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """SPEC-006-002: search() does not require any LLM backend initialization."""
    engine = CodeSight(tmp_path, config=ServerConfig(llm_backend="claude"))
    monkeypatch.setattr(CodeSight, "_ensure_indexed", lambda self: None)
    monkeypatch.setattr(api_module, "hybrid_search", lambda *args, **kwargs: [])

    class _Store:
        pass

    class _Embedder:
        pass

    engine._store = _Store()
    engine._embedder = _Embedder()
    assert engine.search("local query") == []


def test_spec_006_004_answer_model_attribution(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """SPEC-006-004: Answer.model reports backend:model format."""
    engine = CodeSight(tmp_path, config=ServerConfig(llm_backend="ollama", verify=False))
    result = _mk_result()
    monkeypatch.setattr(CodeSight, "search", lambda self, q, top_k=5, file_glob=None: [result])

    class _StubLLM:
        model_id = "openai:gpt-4o"

        def generate_with_citations(self, *_args, **_kwargs):
            return LLMResponse(text="Answer [Source 1]", citations=[])

    engine._llm = _StubLLM()
    answer = engine.ask("question")
    assert answer.model == "openai:gpt-4o"


def test_spec_006_005_azure_requires_deployment_var(monkeypatch: pytest.MonkeyPatch):
    """SPEC-006-005: Azure backend names missing AZURE_OPENAI_DEPLOYMENT."""
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.openai.azure.com/")
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "x")
    monkeypatch.delenv("AZURE_OPENAI_DEPLOYMENT", raising=False)
    with pytest.raises(ValueError, match="AZURE_OPENAI_DEPLOYMENT"):
        get_backend("azure")


def test_edge_006_004_cloud_rate_limit_retries_once(monkeypatch: pytest.MonkeyPatch):
    """EDGE-006-004: Cloud call retries once after a 429 before succeeding."""
    monkeypatch.setattr("codesight.llm.time.sleep", lambda _seconds: None)
    calls = {"count": 0}

    class _RateLimitError(RuntimeError):
        status_code = 429

    def _flaky():
        calls["count"] += 1
        if calls["count"] == 1:
            raise _RateLimitError("429 rate limited")
        return "ok"

    assert _run_cloud_call_with_retry("openai", _flaky) == "ok"
    assert calls["count"] == 2


def test_edge_006_005_timeout_error_has_local_fallback_message():
    """EDGE-006-005: Timeout error mentions the ollama local fallback."""

    class _TimeoutError(RuntimeError):
        pass

    def _always_timeout():
        raise _TimeoutError("request timed out after 30s")

    with pytest.raises(TimeoutError, match="CODESIGHT_LLM_BACKEND=ollama"):
        _run_cloud_call_with_retry("claude", _always_timeout)

