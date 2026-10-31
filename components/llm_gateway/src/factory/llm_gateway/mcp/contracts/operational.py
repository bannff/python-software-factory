"""Typed operational MCP contracts for LLM Gateway."""
from __future__ import annotations

from math import isfinite
from typing import Literal

from pydantic import Field, model_validator

from .base import OutputModel, StrictModel, UsageOutput

ProviderBackend = Literal["bedrock", "openai", "anthropic", "ollama"]
EmbeddingBackend = Literal["bedrock", "openai", "ollama"]
ModelName = str | None


class GenerationInput(StrictModel):
    backend: ProviderBackend = "bedrock"
    model: ModelName = Field(default=None, max_length=512)
    max_tokens: int = Field(default=1024, ge=1, le=8192)
    temperature: float = Field(default=0.7, ge=0, le=2, allow_inf_nan=False)


class CompletionInput(GenerationInput):
    prompt: str = Field(min_length=1, max_length=131_072)


class ChatMessageInput(StrictModel):
    role: Literal["system", "user", "assistant"]
    content: str = Field(min_length=1, max_length=32_768)


class ChatInput(GenerationInput):
    messages: list[ChatMessageInput] = Field(min_length=1, max_length=128)

    @model_validator(mode="after")
    def _aggregate_content_limit(self) -> "ChatInput":
        if sum(len(message.content) for message in self.messages) > 131_072:
            raise ValueError("chat content exceeds 131072 characters")
        return self


class EmbeddingInput(StrictModel):
    texts: list[str] = Field(min_length=1, max_length=128)
    backend: EmbeddingBackend = "bedrock"
    model: ModelName = Field(default=None, max_length=512)

    @model_validator(mode="after")
    def _text_limits(self) -> "EmbeddingInput":
        if any(not text or len(text) > 32_768 for text in self.texts):
            raise ValueError("embedding texts must be non-empty and at most 32768 characters")
        if sum(len(text) for text in self.texts) > 262_144:
            raise ValueError("embedding content exceeds 262144 characters")
        return self


class CompletionOutput(OutputModel):
    content: str = Field(max_length=131_072)
    model: str = Field(min_length=1, max_length=512)
    provider: str = Field(min_length=1, max_length=128)
    usage: UsageOutput
    finish_reason: str = Field(min_length=1, max_length=128)


class EmbeddingOutput(OutputModel):
    embeddings: list[list[float]] = Field(max_length=128)
    model: str = Field(min_length=1, max_length=512)
    provider: str = Field(min_length=1, max_length=128)
    usage: UsageOutput

    @model_validator(mode="after")
    def _embedding_bounds(self) -> "EmbeddingOutput":
        if any(
            not row or len(row) > 8192 or any(not isfinite(value) for value in row)
            for row in self.embeddings
        ):
            raise ValueError("embeddings must be finite vectors of at most 8192 dimensions")
        return self


__all__ = [
    "ChatInput",
    "ChatMessageInput",
    "CompletionInput",
    "CompletionOutput",
    "EmbeddingInput",
    "EmbeddingOutput",
]
