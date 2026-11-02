"""Embedding port and adapter for memory brick.

Provides semantic embeddings for memory content via llm_gateway.
Uses the EmbeddingProvider protocol — no hardcoded backends.
"""

from __future__ import annotations

import logging
from typing import Any, Protocol

logger = logging.getLogger(__name__)


class MemoryEmbedder(Protocol):
    """Port: Generate embeddings for memory content."""

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return embedding vectors for the given texts."""
        ...

    @property
    def dimensions(self) -> int:
        """Return the embedding dimensionality."""
        ...


class LLMGatewayEmbedder:
    """Adapter: Use llm_gateway's EmbeddingProvider for memory embeddings."""

    def __init__(self, backend: str | None = None, model: str | None = None) -> None:
        # backend None = the gateway's FACTORY_LLM_EMBEDDING_ADAPTER (no hardcoded cloud).
        self._backend = backend
        self._model = model
        self._provider: Any = None
        self._dims: int | None = None

    def _get_provider(self) -> Any:
        if self._provider is None:
            from factory.llm_gateway.interface import LLMRuntime
            runtime = LLMRuntime()
            self._provider = runtime.get_embedder(self._backend)
        return self._provider

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings via llm_gateway."""
        if not texts:
            return []
        provider = self._get_provider()
        kwargs: dict[str, Any] = {}
        if self._model:
            kwargs["model"] = self._model
        response = provider.embed(texts, **kwargs)
        vectors = response.embeddings
        if vectors and len(vectors[0]) != self._dims:
            self._dims = len(vectors[0])
        return vectors

    @property
    def label(self) -> str:
        """Human-readable provider/model for status displays."""
        return f"{self._backend or 'gateway default'}/{self._model or 'default model'}"

    @property
    def dimensions(self) -> int:
        """Vector size, learned once by embedding a probe string (0 = unavailable)."""
        if self._dims is None:
            try:
                self.embed(["dimension probe"])
            except Exception as exc:  # noqa: BLE001 - no provider means no vectors
                logger.warning("embedding provider unavailable: %s", exc)
                self._dims = 0
        return self._dims or 0


class NoOpEmbedder:
    """Null adapter: returns empty vectors (for testing or no-embed mode)."""

    def embed(self, texts: list[str]) -> list[list[float]]:
        return []

    @property
    def dimensions(self) -> int:
        return 0
