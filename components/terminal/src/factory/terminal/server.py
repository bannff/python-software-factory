"""Terminal MCP server composition (pure transport shell)."""
from __future__ import annotations

from typing import Any

from .mcp import deterministic, operational
from .runtime.runtime import TerminalRuntime, get_runtime


def create_tool_catalog(runtime: TerminalRuntime | None = None) -> Any:
    from factory.mcp_utils.runtime.tool_catalog import ToolCatalog

    active = runtime or get_runtime()
    catalog = ToolCatalog("terminal-module")
    deterministic.register(catalog, active)
    operational.register(catalog, active)
    return catalog


def create_mcp_server(runtime: TerminalRuntime | None = None) -> Any:
    return create_tool_catalog(runtime)


def get_capabilities() -> dict[str, Any]:
    return {
        "name": "terminal", "version": "0.1.0", "adapter": "posix_pty",
        "features": ["interactive_pty", "shell_discovery", "resize", "scrollback"],
    }


def health_check() -> dict[str, Any]:
    return {"healthy": True, "adapter": "posix_pty"}


def describe_config_schema() -> dict[str, Any]:
    return {
        "type": "object", "additionalProperties": False,
        "properties": {
            "max_sessions": {"type": "integer", "default": 12},
            "orphan_timeout_seconds": {"type": "integer", "default": 900},
        },
    }


__all__ = [
    "create_mcp_server", "create_tool_catalog", "describe_config_schema",
    "get_capabilities", "health_check",
]
