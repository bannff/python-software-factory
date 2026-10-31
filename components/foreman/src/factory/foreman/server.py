"""Neutral MCP catalog for Foreman workspace management."""
from typing import Any

from .core import build_bricks_index
from .mcp import resources, prompts, tools
from factory.mcp_utils.server import make_lazy_runner
from factory.mcp_utils.runtime.tool_catalog import ToolCatalog


def create_tool_catalog() -> ToolCatalog:
    """Create Foreman's complete transport-neutral catalog."""
    catalog = ToolCatalog("python-factory")
    resources.register(catalog, build_bricks_index)
    prompts.register(catalog)
    tools.register(catalog)
    return catalog


def create_mcp_server() -> ToolCatalog:
    """Return the canonical framework-neutral catalog."""
    return create_tool_catalog()


def get_capabilities() -> dict[str, Any]:
    return {
        "name": "foreman", "version": "1.0.0", "backends": ["polylith"],
        "features": ["workspace_management", "brick_indexing", "compliance_checks", "scaffolding"],
    }


def health_check() -> dict[str, Any]:
    return {"healthy": True, "workspace": "python-factory"}


def describe_config_schema() -> dict[str, Any]:
    return {"type": "object", "properties": {
        "workspace_root": {"type": "string", "description": "Workspace root directory"},
    }}


get_mcp_server, main = make_lazy_runner(create_mcp_server)
create_server = create_mcp_server

if __name__ == "__main__":
    main()
