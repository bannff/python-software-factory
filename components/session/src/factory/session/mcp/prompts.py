"""MCP prompts for session management."""
from __future__ import annotations

from typing import Any, Callable


def register(mcp: Any, get_runtime: Callable[[], Any]) -> None:
    del get_runtime

    @mcp.prompt(name="manage_session")
    def manage_session() -> str:
        return "Manage only sessions owned by the authenticated tenant and principal."


__all__ = ["register"]
