"""OpenArcade framework-neutral MCP catalog."""
from __future__ import annotations

from typing import Any

from factory.mcp_utils.server import make_lazy_runner
from factory.mcp_utils.runtime.tool_catalog import ToolCatalog
from .mcp import deterministic, operational, prompts, resources
from .runtime import get_runtime


def create_tool_catalog() -> ToolCatalog:
    runtime = get_runtime()
    get_current = lambda: runtime
    catalog = ToolCatalog("factory-openarcade")
    deterministic.register(catalog, get_current)
    operational.register(catalog, get_current)
    resources.register(catalog, get_current)
    prompts.register(catalog, get_current)
    return catalog


def create_mcp_server() -> ToolCatalog:
    """Return the canonical framework-neutral catalog."""
    return create_tool_catalog()


get_mcp_server, main = make_lazy_runner(create_mcp_server)

if __name__ == "__main__":
    main()
