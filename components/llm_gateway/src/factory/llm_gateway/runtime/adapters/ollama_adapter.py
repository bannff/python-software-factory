"""Ollama adapter for LLM Gateway.

Uses Ollama's OpenAI-compatible API surface so Companion-X can treat
Ollama as a first-class backend while keeping provider selection explicit.
"""

from __future__ import annotations

import os
from typing import Any

from .openai_adapter import OpenAIProvider, OpenAIEmbedder


class OllamaProvider(OpenAIProvider):
    """Ollama chat/completion adapter via OpenAI-compatible endpoints."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        **kwargs: Any,
    ) -> None:
        resolved_base_url = base_url or os.getenv(
            "OLLAMA_BASE_URL", "http://localhost:11434/v1"
        )
        resolved_api_key = api_key or os.getenv("OLLAMA_API_KEY") or "ollama"
        resolved_model = model or os.getenv("OLLAMA_MODEL", "llama3.2")
        super().__init__(
            api_key=resolved_api_key,
            model=resolved_model,
            base_url=resolved_base_url,
            **kwargs,
        )


class OllamaEmbedder(OpenAIEmbedder):
    """Ollama embedding adapter via OpenAI-compatible endpoints."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "nomic-embed-text",
        base_url: str | None = None,
        **kwargs: Any,
    ) -> None:
        resolved_base_url = base_url or os.getenv(
            "OLLAMA_BASE_URL", "http://localhost:11434/v1"
        )
        resolved_api_key = api_key or os.getenv("OLLAMA_API_KEY") or "ollama"
        super().__init__(
            api_key=resolved_api_key,
            model=model,
            base_url=resolved_base_url,
            **kwargs,
        )