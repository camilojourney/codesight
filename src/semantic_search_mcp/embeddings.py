"""Embedding model wrapper — swappable interface for generating vectors."""

from __future__ import annotations

import logging
from functools import lru_cache

import numpy as np

from .config import DEFAULT_EMBEDDING_DIM, DEFAULT_EMBEDDING_MODEL

logger = logging.getLogger(__name__)


class Embedder:
    """Wraps a sentence-transformers model for embedding code chunks.

    The model is lazily loaded on first use and cached for the process lifetime.
    """

    def __init__(
        self,
        model_name: str = DEFAULT_EMBEDDING_MODEL,
        expected_dim: int = DEFAULT_EMBEDDING_DIM,
    ) -> None:
        self.model_name = model_name
        self.expected_dim = expected_dim
        self._model = None

    @property
    def model(self):
        """Lazy-load the model on first access."""
        if self._model is None:
            logger.info("Loading embedding model: %s", self.model_name)
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self.model_name)
            actual_dim = self._model.get_sentence_embedding_dimension()
            if actual_dim != self.expected_dim:
                logger.warning(
                    "Model dimension %d != expected %d. Update config.",
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
            show_progress_bar=False,
            convert_to_numpy=True,
            normalize_embeddings=True,  # cosine sim = dot product when normalized
        )
        return embeddings.astype(np.float32)

    def embed_query(self, query: str) -> np.ndarray:
        """Embed a single query string, returning a (dim,) float32 array."""
        return self.embed([query])[0]


@lru_cache(maxsize=1)
def get_embedder(
    model_name: str = DEFAULT_EMBEDDING_MODEL,
    expected_dim: int = DEFAULT_EMBEDDING_DIM,
) -> Embedder:
    """Return a cached Embedder singleton."""
    return Embedder(model_name=model_name, expected_dim=expected_dim)
