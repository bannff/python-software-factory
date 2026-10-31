"""Authoring (security-gated) MCP tools for graph module.

No authoring tools defined yet — placeholder for future config-changing tools
per brick-anatomy.md. Future tools (e.g. schema mutations, backend re-config)
will go here, gated by ``factory.mcp_utils.interface.authoring``.
"""

from __future__ import annotations

from typing import Callable, TYPE_CHECKING

from typing import Any

if TYPE_CHECKING:
    from ..runtime.runtime import GraphRuntime


def register(mcp: Any, get_runtime: Callable[[], "GraphRuntime"]) -> None:
    """Register authoring tools with the MCP server (currently none)."""
    pass
