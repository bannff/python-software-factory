"""Core convenience functions for llm_gateway brick.

Provides simple top-level functions for common LLM operations.
"""

from __future__ import annotations

from typing import Any

from .runtime.ports import LLMMessage, LLMResponse, EmbeddingResponse
from .runtime.runtime import get_runtime


def complete(
    prompt: str,
    model: str | None = None,
    backend: str = "bedrock",
    max_tokens: int = 1024,
    temperature: float = 0.7,
    **kwargs: Any,
) -> LLMResponse:
    """Generate a text completion.

    Args:
        prompt: The prompt text
        model: Model ID (uses backend default if not specified)
        backend: Provider backend (bedrock, openai, anthropic)
        max_tokens: Maximum tokens to generate
        temperature: Sampling temperature
        **kwargs: Additional provider-specific options

    Returns:
        LLMResponse with generated content
    """
    runtime = get_runtime()
    provider = runtime.get_provider(backend)
    return provider.complete(prompt, model, max_tokens, temperature, **kwargs)


def chat(
    messages: list[dict[str, str]] | list[LLMMessage],
    model: str | None = None,
    backend: str = "bedrock",
    max_tokens: int = 1024,
    temperature: float = 0.7,
    **kwargs: Any,
) -> LLMResponse:
    """Generate a chat completion.

    Args:
        messages: List of messages (dicts with role/content or LLMMessage objects)
        model: Model ID (uses backend default if not specified)
        backend: Provider backend (bedrock, openai, anthropic)
        max_tokens: Maximum tokens to generate
        temperature: Sampling temperature
        **kwargs: Additional provider-specific options

    Returns:
        LLMResponse with generated content
    """
    runtime = get_runtime()
    provider = runtime.get_provider(backend)

    # Convert dicts to LLMMessage if needed
    llm_messages = [
        LLMMessage(role=m["role"], content=m["content"]) if isinstance(m, dict) else m
        for m in messages
    ]

    return provider.chat(llm_messages, model, max_tokens, temperature, **kwargs)


def embed(
    texts: list[str],
    model: str | None = None,
    backend: str = "bedrock",
    **kwargs: Any,
) -> EmbeddingResponse:
    """Generate embeddings for texts.

    Args:
        texts: List of texts to embed
        model: Model ID (uses backend default if not specified)
        backend: Provider backend (bedrock, openai)
        **kwargs: Additional provider-specific options

    Returns:
        EmbeddingResponse with embedding vectors
    """
    runtime = get_runtime()
    embedder = runtime.get_embedder(backend)
    return embedder.embed(texts, model, **kwargs)


async def complete_async(
    prompt: str,
    model: str | None = None,
    backend: str = "bedrock",
    max_tokens: int = 1024,
    temperature: float = 0.7,
    **kwargs: Any,
) -> LLMResponse:
    """Async text completion."""
    runtime = get_runtime()
    provider = runtime.get_provider(backend)
    return await provider.complete_async(prompt, model, max_tokens, temperature, **kwargs)


async def chat_async(
    messages: list[dict[str, str]] | list[LLMMessage],
    model: str | None = None,
    backend: str = "bedrock",
    max_tokens: int = 1024,
    temperature: float = 0.7,
    **kwargs: Any,
) -> LLMResponse:
    """Async chat completion."""
    runtime = get_runtime()
    provider = runtime.get_provider(backend)

    llm_messages = [
        LLMMessage(role=m["role"], content=m["content"]) if isinstance(m, dict) else m
        for m in messages
    ]

    return await provider.chat_async(llm_messages, model, max_tokens, temperature, **kwargs)


async def embed_async(
    texts: list[str],
    model: str | None = None,
    backend: str = "bedrock",
    **kwargs: Any,
) -> EmbeddingResponse:
    """Async embedding."""
    runtime = get_runtime()
    embedder = runtime.get_embedder(backend)
    return await embedder.embed_async(texts, model, **kwargs)
