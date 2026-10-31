"""Abstract ports for llm_gateway brick.

Ports define what capabilities the LLM gateway needs, not how they're implemented.
Adapters plug in specific providers (Bedrock, OpenAI, Anthropic, etc.)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class LLMHealth:
    """Health status for an LLM provider."""
    healthy: bool
    provider: str
    latency_ms: float = 0.0
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class LLMMessage:
    """A chat message."""
    role: str  # "system", "user", "assistant"
    content: str


@dataclass
class LLMResponse:
    """Response from an LLM call."""
    content: str
    model: str
    provider: str
    usage: dict[str, int] = field(default_factory=dict)  # input_tokens, output_tokens
    finish_reason: str = "stop"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class EmbeddingResponse:
    """Response from an embedding call."""
    embeddings: list[list[float]]
    model: str
    provider: str
    usage: dict[str, int] = field(default_factory=dict)


class LLMProvider(Protocol):
    """Port: LLM provider for completions and chat."""

    def complete(
        self,
        prompt: str,
        model: str | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.7,
        **kwargs: Any,
    ) -> LLMResponse:
        """Generate a text completion."""
        ...

    def chat(
        self,
        messages: list[LLMMessage],
        model: str | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.7,
        **kwargs: Any,
    ) -> LLMResponse:
        """Generate a chat completion."""
        ...

    async def complete_async(
        self,
        prompt: str,
        model: str | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.7,
        **kwargs: Any,
    ) -> LLMResponse:
        """Generate a text completion asynchronously."""
        ...

    async def chat_async(
        self,
        messages: list[LLMMessage],
        model: str | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.7,
        **kwargs: Any,
    ) -> LLMResponse:
        """Generate a chat completion asynchronously."""
        ...

    def health_check(self) -> LLMHealth:
        """Check provider health."""
        ...


class EmbeddingProvider(Protocol):
    """Port: Embedding provider."""

    def embed(
        self,
        texts: list[str],
        model: str | None = None,
        **kwargs: Any,
    ) -> EmbeddingResponse:
        """Generate embeddings for texts."""
        ...

    async def embed_async(
        self,
        texts: list[str],
        model: str | None = None,
        **kwargs: Any,
    ) -> EmbeddingResponse:
        """Generate embeddings asynchronously."""
        ...

    def health_check(self) -> LLMHealth:
        """Check provider health."""
        ...
