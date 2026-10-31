"""LLM Gateway brick - direct LLM calls with pluggable providers.

This brick provides a unified interface for LLM completions and embeddings
across multiple providers (Bedrock, OpenAI, Anthropic).

Usage:
    from factory.llm_gateway import complete, chat, embed

    # Simple completion
    response = complete("What is 2+2?", backend="openai")
    print(response.content)

    # Chat completion
    response = chat([
        {"role": "system", "content": "You are helpful."},
        {"role": "user", "content": "Hello!"},
    ], backend="anthropic")

    # Embeddings
    response = embed(["Hello world"], backend="bedrock")
    print(response.embeddings[0][:5])  # First 5 dimensions
"""

from .interface import (
    LLMProvider,
    EmbeddingProvider,
    LLMMessage,
    LLMResponse,
    EmbeddingResponse,
    LLMHealth,
    LLMRuntime,
    get_runtime,
    reset_runtime,
)
from .core import (
    complete,
    chat,
    embed,
    complete_async,
    chat_async,
    embed_async,
)

__all__ = [
    # Ports
    "LLMProvider",
    "EmbeddingProvider",
    # Data classes
    "LLMMessage",
    "LLMResponse",
    "EmbeddingResponse",
    "LLMHealth",
    # Runtime
    "LLMRuntime",
    "get_runtime",
    "reset_runtime",
    # Convenience functions
    "complete",
    "chat",
    "embed",
    "complete_async",
    "chat_async",
    "embed_async",
]
