"""LLM Gateway runtime factory - selects and configures LLM providers.

Usage:
    runtime = LLMRuntime()
    llm = runtime.get_provider("bedrock")  # or "openai", "anthropic", "ollama"
    embedder = runtime.get_embedder("bedrock")
"""

from __future__ import annotations

import logging
import os
from typing import Any

from .ports import LLMProvider, EmbeddingProvider, LLMHealth

logger = logging.getLogger(__name__)


class LLMRuntime:
    """Factory for creating LLM provider adapters."""

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self._config = config or {}
        self._providers: dict[str, LLMProvider] = {}
        self._embedders: dict[str, EmbeddingProvider] = {}

    def get_provider(self, backend: str | None = None, **kwargs: Any) -> LLMProvider:
        """Get or create an LLM provider adapter."""
        backend = self._resolve_provider_backend(backend)
        key = f"{backend}:{hash(frozenset(kwargs.items()))}"
        if key not in self._providers:
            self._providers[key] = self._create_provider(backend, **kwargs)
        return self._providers[key]

    def get_embedder(self, backend: str | None = None, **kwargs: Any) -> EmbeddingProvider:
        """Get or create an embedding provider adapter."""
        backend = self._resolve_embedder_backend(backend)
        key = f"{backend}:{hash(frozenset(kwargs.items()))}"
        if key not in self._embedders:
            self._embedders[key] = self._create_embedder(backend, **kwargs)
        return self._embedders[key]

    def _resolve_provider_backend(self, backend: str | None) -> str:
        if backend:
            return backend
        return os.environ.get("FACTORY_LLM_ADAPTER", "bedrock").lower()

    def _resolve_embedder_backend(self, backend: str | None) -> str:
        if backend:
            return backend
        preferred = os.environ.get(
            "FACTORY_LLM_EMBEDDING_ADAPTER",
            os.environ.get("FACTORY_LLM_ADAPTER", "bedrock"),
        ).lower()
        if preferred in {"bedrock", "openai", "ollama"}:
            return preferred
        return "bedrock"

    def _create_provider(self, backend: str, **kwargs: Any) -> LLMProvider:
        """Create an LLM provider adapter."""
        if backend == "bedrock":
            from .adapters.bedrock_adapter import BedrockProvider
            return BedrockProvider(**kwargs)
        elif backend == "openai":
            from .adapters.openai_adapter import OpenAIProvider
            return OpenAIProvider(**kwargs)
        elif backend == "anthropic":
            from .adapters.anthropic_adapter import AnthropicProvider
            return AnthropicProvider(**kwargs)
        elif backend == "ollama":
            from .adapters.ollama_adapter import OllamaProvider
            return OllamaProvider(**kwargs)
        raise ValueError(f"Unknown LLM backend: {backend}. Available: {self.available_backends()}")

    def _create_embedder(self, backend: str, **kwargs: Any) -> EmbeddingProvider:
        """Create an embedding provider adapter."""
        if backend == "bedrock":
            from .adapters.bedrock_adapter import BedrockEmbedder
            return BedrockEmbedder(**kwargs)
        elif backend == "openai":
            from .adapters.openai_adapter import OpenAIEmbedder
            return OpenAIEmbedder(**kwargs)
        elif backend == "ollama":
            from .adapters.ollama_adapter import OllamaEmbedder
            return OllamaEmbedder(**kwargs)
        raise ValueError(f"Unknown embedding backend: {backend}. Available: bedrock, openai, ollama")

    def health_check(self) -> dict[str, LLMHealth]:
        """Check health of all active providers."""
        results: dict[str, LLMHealth] = {}
        for name, provider in self._providers.items():
            results[f"llm:{name}"] = provider.health_check()
        for name, embedder in self._embedders.items():
            results[f"embed:{name}"] = embedder.health_check()
        return results

    @staticmethod
    def available_backends() -> list[str]:
        """List available LLM backends."""
        return ["bedrock", "openai", "anthropic", "ollama"]


_runtime: LLMRuntime | None = None


def get_runtime() -> LLMRuntime:
    """Get the global LLM runtime."""
    global _runtime
    if _runtime is None:
        _runtime = LLMRuntime()
    return _runtime


def reset_runtime() -> None:
    """Reset the global runtime (for testing)."""
    global _runtime
    _runtime = None
