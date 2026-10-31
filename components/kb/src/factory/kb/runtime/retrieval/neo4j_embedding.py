"""Embedding adapter for KB brick's Neo4j vector store.

Wraps llm_gateway's EmbeddingProvider for use in the KB brick.
No cross-brick imports from memory or graph — only llm_gateway.interface.
"""

from __future__ import annotations

import logging
from typing import Any, Protocol

logger = logging.getLogger(__name__)


class KBEmbedder(Protocol):
    """Port: Generate embeddings for KB documents."""

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return embedding vectors for the given texts."""
        ...

    @property
    def dimensions(self) -> int:
        """Return the embedding dimensionality."""
        ...


class LLMGatewayKBEmbedder:
    """Adapter: Use llm_gateway's EmbeddingProvider for KB embeddings."""

    def __init__(self, backend: str = "bedrock", model: str | None = None) -> None:
        self._backend = backend
        self._model = model
        self._provider: Any = None
        self._dims: int = 1024  # Titan v2 default

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
    def dimensions(self) -> int:
        return self._dims


class NoOpKBEmbedder:
    """Null adapter: returns empty vectors (for testing or no-embed mode)."""

    def embed(self, texts: list[str]) -> list[list[float]]:
        return []

    @property
    def dimensions(self) -> int:
        return 0
