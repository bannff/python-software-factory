"""MCP tool registration for the KB brick."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable
from . import deterministic, operational, authoring, views


def register_tools(
    mcp: Any,
    *,
    get_runtime: Callable[[], Any],
    get_authoring: Callable[[], Any],
    get_config_dir: Callable[[], Path],
) -> None:
    """Register all KB tools with the provided MCP server."""
    deterministic.register(mcp, get_runtime, get_authoring, get_config_dir)
    operational.register(mcp, get_runtime)
    authoring.register(mcp, get_authoring)
    views.register(mcp)
