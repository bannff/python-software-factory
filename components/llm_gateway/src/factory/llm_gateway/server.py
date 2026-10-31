"""LLM Gateway MCP server and safe compatibility helpers."""
from __future__ import annotations

from typing import Any

from factory.mcp_utils.server import make_lazy_runner

from .mcp import deterministic, operational, prompts, resources
from .runtime.runtime import LLMRuntime, get_runtime


def _register_tools(registry: Any, runtime: LLMRuntime) -> None:
    get_current = lambda: runtime
    deterministic.register(registry, get_current)
    operational.register(registry, get_current)


def create_tool_catalog(runtime: LLMRuntime | None = None) -> Any:
    """Create the transport-neutral LLM Gateway tool catalog."""
    from factory.mcp_utils.runtime.tool_catalog import ToolCatalog

    active_runtime = runtime or get_runtime()
    catalog = ToolCatalog("factory-llm-gateway")
    _register_tools(catalog, active_runtime)
    get_current = lambda: active_runtime
    resources.register(catalog, get_current)
    prompts.register(catalog, get_current)
    return catalog


def create_mcp_server(runtime: LLMRuntime | None = None) -> Any:
    """Return the canonical framework-neutral catalog."""
    return create_tool_catalog(runtime)


def get_capabilities() -> dict[str, object]:
    """Return the same truthful capability projection as the MCP tool."""
    return {
        "name": "llm_gateway", "version": "2.0.0",
        "backends": LLMRuntime.available_backends(),
        "features": ["text_completion", "chat_completion", "embeddings", "async_support"],
    }


def health_check() -> dict[str, object]:
    """Return a safe compatibility health projection without error text."""
    return resources.safe_health_projection(get_runtime())


def describe_config_schema() -> dict[str, object]:
    """Return the safe compatibility configuration projection."""
    return resources.config_schema()


get_mcp_server, main = make_lazy_runner(create_mcp_server)

if __name__ == "__main__":
    main()
