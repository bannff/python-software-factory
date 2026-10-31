"""Strict typed deterministic MCP tools for the LLM Gateway brick."""
from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from typing import Any

from factory.mcp_utils.interface import ToolResult, deterministic, ok
from factory.mcp_utils.registration import typed_tool

from .contracts import (
    BackendsOutput,
    CapabilitiesOutput,
    ConfigProperty,
    ConfigSchemaOutput,
    EmptyInput,
    HealthOutput,
    ProviderHealth,
)

if TYPE_CHECKING:
    from ..runtime.runtime import LLMRuntime

_BACKENDS = ["bedrock", "openai", "anthropic", "ollama"]
_EMBEDDING_BACKENDS = ["bedrock", "openai", "ollama"]


def register(mcp: Any, get_runtime: Callable[[], "LLMRuntime"]) -> None:
    """Register strict deterministic tools with raw flat ingress."""

    @typed_tool(mcp)
    @deterministic(input_model=EmptyInput, output_model=CapabilitiesOutput)
    def get_capabilities() -> ToolResult[CapabilitiesOutput]:
        """Return machine-readable capabilities for llm_gateway."""
        return ok(CapabilitiesOutput(
            name="llm_gateway",
            version="2.0.0",
            backends=_BACKENDS,
            features=["text_completion", "chat_completion", "embeddings", "async_support"],
        ))

    @typed_tool(mcp)
    @deterministic(input_model=EmptyInput, output_model=HealthOutput)
    def health_check() -> ToolResult[HealthOutput]:
        """Return a secret-safe readiness projection of active providers."""
        health = get_runtime().health_check()
        providers = {
            name: ProviderHealth(healthy=status.healthy, provider=status.provider)
            for name, status in health.items()
        }
        return ok(HealthOutput(
            healthy=all(status.healthy for status in health.values()) if health else True,
            providers=providers,
        ))

    @typed_tool(mcp)
    @deterministic(input_model=EmptyInput, output_model=ConfigSchemaOutput)
    def describe_config_schema() -> ToolResult[ConfigSchemaOutput]:
        """Describe safe server-owned MCP configuration fields."""
        return ok(ConfigSchemaOutput(
            type="object",
            properties={
                "backend": ConfigProperty(
                    type="string", enum=_BACKENDS,
                    description="Server-configured LLM provider backend",
                ),
                "model": ConfigProperty(
                    type="string", description="Provider-specific model identifier",
                ),
            },
        ))

    @typed_tool(mcp)
    @deterministic(input_model=EmptyInput, output_model=BackendsOutput)
    def llm_list_backends() -> ToolResult[BackendsOutput]:
        """List supported completion/chat and embedding backends."""
        return ok(BackendsOutput(
            backends=_BACKENDS,
            embedding_backends=_EMBEDDING_BACKENDS,
        ))


__all__ = ["register"]
