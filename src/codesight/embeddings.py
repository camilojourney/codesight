"""Embedding model wrapper — local (sentence-transformers) or API (OpenAI).

Backend is selected via CODESIGHT_EMBEDDING_BACKEND env var:
  - local  (default) — runs on CPU/GPU, no API key, no data leaves
  - api    — OpenAI text-embedding-3-large, best quality
"""

from __future__ import annotations

import logging
import os
import time
from functools import lru_cache
from typing import Protocol

import numpy as np

from .config import (
    DEFAULT_EMBEDDING_BACKEND,
    DEFAULT_EMBEDDING_DIM,
    DEFAULT_EMBEDDING_MODEL,
    normalize_embedding_model_name,
    resolve_embedding_dim,
    validate_embedding_model,
)

logger = logging.getLogger(__name__)

_LOCAL_MODEL_IDS: dict[str, str] = {
    "nomic-embed-text-v1.5": "nomic-ai/nomic-embed-text-v1.5",
    "all-MiniLM-L6-v2": "sentence-transformers/all-MiniLM-L6-v2",
    "mxbai-embed-large": "mixedbread-ai/mxbai-embed-large-v1",
    "jina-embeddings-v2-base-code": "jinaai/jina-embeddings-v2-base-code",
}


def _is_rate_limit_error(exc: Exception) -> bool:
    status_code = getattr(exc, "status_code", None)
    if status_code == 429:
        return True
    message = str(exc).lower()
    return "429" in message or "rate limit" in message or "ratelimit" in message


def _is_network_error(exc: Exception) -> bool:
    message = str(exc).lower()
    markers = ("connect", "unreachable", "dns", "timed out", "timeout", "connection")
    return any(marker in message for marker in markers)


class Embedder(Protocol):
    """Protocol for embedding backends."""

    model_name: str
    expected_dim: int

    def embed(self, texts: list[str]) -> np.ndarray: ...
    def embed_query(self, query: str) -> np.ndarray: ...


# ---------------------------------------------------------------------------
# Local backend (sentence-transformers)
# ---------------------------------------------------------------------------


class LocalEmbedder:
    """Wraps a sentence-transformers model for embedding.

    The model is lazily loaded on first use and cached for the process lifetime.
    """

    def __init__(
        self,
        model_name: str = DEFAULT_EMBEDDING_MODEL,
        expected_dim: int = DEFAULT_EMBEDDING_DIM,
    ) -> None:
        self.model_name = normalize_embedding_model_name(model_name)
        self._runtime_model_id = _LOCAL_MODEL_IDS.get(self.model_name, self.model_name)
        self.expected_dim = expected_dim
        self._model = None

    @property
    def model(self):
        """Lazy-load the model on first access."""
        if self._model is None:
            logger.info("Loading embedding model: %s", self.model_name)
            from sentence_transformers import SentenceTransformer

            try:
                self._model = SentenceTransformer(self._runtime_model_id, trust_remote_code=True)
            except Exception as exc:
                # EDGE-002-001: Clear install/download guidance for missing local models.
                raise ValueError(
                    f"Model '{self.model_name}' not found locally. Install via: "
                    "python -c 'from sentence_transformers import SentenceTransformer; "
                    f"SentenceTransformer(\"{self.model_name}\")' or run "
                    "pip install sentence-transformers first."
                ) from exc
            actual_dim = self._model.get_sentence_embedding_dimension()
            if actual_dim != self.expected_dim:
                logger.warning(
                    "Model dimension %d != expected %d. Updating.",
                    actual_dim,
                    self.expected_dim,
                )
                self.expected_dim = actual_dim
        return self._model

    def embed(self, texts: list[str]) -> np.ndarray:
        """Embed a list of texts, returning an (N, dim) float32 array."""
        if not texts:
            return np.empty((0, self.expected_dim), dtype=np.float32)
        embeddings = self.model.encode(
            texts,
            show_progress_bar=len(texts) > 100,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )
        return embeddings.astype(np.float32)

    def embed_query(self, query: str) -> np.ndarray:
        """Embed a single query string, returning a (dim,) float32 array."""
        return self.embed([query])[0]


# ---------------------------------------------------------------------------
# API backend (OpenAI)
# ---------------------------------------------------------------------------


class APIEmbedder:
    """OpenAI embedding API backend — best quality, requires API key."""

    def __init__(
        self,
        model_name: str = "text-embedding-3-large",
        expected_dim: int = 3072,
    ) -> None:
        self._api_key = os.environ.get("OPENAI_API_KEY")
        if not self._api_key:
            raise ValueError(
                "OPENAI_API_KEY environment variable is required for API embedding backend. "
                "Set it or switch to local: CODESIGHT_EMBEDDING_BACKEND=local"
            )
        self.model_name = normalize_embedding_model_name(model_name)
        self.expected_dim = expected_dim
        self._client = None

    @property
    def client(self):
        if self._client is None:
            from openai import OpenAI
            self._client = OpenAI(api_key=self._api_key, timeout=30)
        return self._client

    def embed(self, texts: list[str]) -> np.ndarray:
        """Embed texts via OpenAI API in batches of 512."""
        # SPEC-002-004: API backend embeds in bounded batches for payload safety.
        if not texts:
            return np.empty((0, self.expected_dim), dtype=np.float32)

        all_embeddings = []
        batch_size = 512
        total_batches = (len(texts) + batch_size - 1) // batch_size

        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            batch_num = (i // batch_size) + 1
            if len(texts) > batch_size:
                logger.info(
                    "Embedding batch %d/%d via OpenAI (%d texts)",
                    batch_num,
                    total_batches,
                    len(batch),
                )

            attempts = 0
            while True:
                try:
                    response = self.client.embeddings.create(
                        model=self.model_name,
                        input=batch,
                    )
                    break
                except Exception as exc:
                    # EDGE-002-003: 429s get bounded exponential backoff.
                    if _is_rate_limit_error(exc):
                        if attempts < 3:
                            wait_seconds = 2**attempts
                            time.sleep(wait_seconds)
                            attempts += 1
                            continue
                        raise RuntimeError(
                            "OpenAI embedding API rate limited after 3 retries. "
                            "Reduce batch size or wait before re-indexing."
                        ) from None
                    # EDGE-002-002: Network failures suggest local fallback.
                    if _is_network_error(exc):
                        raise ConnectionError(
                            "OpenAI embedding API unreachable. "
                            "Set CODESIGHT_EMBEDDING_BACKEND=local to use a local model "
                            "with no network dependency."
                        ) from None
                    raise

            batch_vecs = [item.embedding for item in response.data]
            if batch_vecs:
                actual_dim = len(batch_vecs[0])
                if actual_dim != self.expected_dim:
                    raise ValueError(
                        f"Embedding dimension mismatch for {self.model_name}: "
                        f"expected {self.expected_dim}, got {actual_dim}"
                    )
            all_embeddings.extend(batch_vecs)

        result = np.array(all_embeddings, dtype=np.float32)
        # Normalize for cosine similarity
        norms = np.linalg.norm(result, axis=1, keepdims=True)
        norms[norms == 0] = 1
        result = result / norms
        return result

    def embed_query(self, query: str) -> np.ndarray:
        """Embed a single query string."""
        return self.embed([query])[0]


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def get_embedder(
    model_name: str = DEFAULT_EMBEDDING_MODEL,
    expected_dim: int = DEFAULT_EMBEDDING_DIM,
    backend: str = DEFAULT_EMBEDDING_BACKEND,
) -> Embedder:
    """Return a cached Embedder singleton.

    Args:
        model_name: Model identifier from the registry or a custom HuggingFace model.
        expected_dim: Expected embedding dimension.
        backend: 'local' for sentence-transformers, 'api' for OpenAI.
    """
    canonical_model = validate_embedding_model(model_name, backend)
    if expected_dim != DEFAULT_EMBEDDING_DIM:
        dim = expected_dim
    else:
        dim = resolve_embedding_dim(canonical_model)

    if backend == "api":
        logger.info("Using API embedding backend: %s", canonical_model)
        return APIEmbedder(model_name=canonical_model, expected_dim=dim)

    logger.info("Using local embedding backend: %s", canonical_model)
    return LocalEmbedder(model_name=canonical_model, expected_dim=dim)
