"""Typed deterministic MCP contracts for LLM Gateway."""
from __future__ import annotations

from typing import Literal

from pydantic import Field

from .base import OutputModel


class CapabilitiesOutput(OutputModel):
    name: Literal["llm_gateway"]
    version: str = Field(min_length=1, max_length=64)
    backends: list[Literal["bedrock", "openai", "anthropic", "ollama"]]
    features: list[Literal["text_completion", "chat_completion", "embeddings", "async_support"]]


class ProviderHealth(OutputModel):
    healthy: bool
    provider: str = Field(min_length=1, max_length=128)


class HealthOutput(OutputModel):
    healthy: bool
    providers: dict[str, ProviderHealth]


class ConfigProperty(OutputModel):
    type: Literal["string"]
    description: str = Field(min_length=1, max_length=256)
    enum: list[Literal["bedrock", "openai", "anthropic", "ollama"]] | None = None


class ConfigSchemaOutput(OutputModel):
    type: Literal["object"]
    properties: dict[Literal["backend", "model"], ConfigProperty]


class BackendsOutput(OutputModel):
    backends: list[Literal["bedrock", "openai", "anthropic", "ollama"]]
    embedding_backends: list[Literal["bedrock", "openai", "ollama"]]


__all__ = [
    "BackendsOutput",
    "CapabilitiesOutput",
    "ConfigProperty",
    "ConfigSchemaOutput",
    "HealthOutput",
    "ProviderHealth",
]
