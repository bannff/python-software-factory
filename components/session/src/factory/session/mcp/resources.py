"""MCP resources for session contracts."""
from __future__ import annotations

from typing import Any, Callable

from ..runtime.models import SessionRecord, SteerMessage


def register(mcp: Any, get_runtime: Callable[[], Any]) -> None:
    del get_runtime

    @mcp.resource("session://schemas/session")
    def session_schema() -> dict[str, Any]:
        return SessionRecord.model_json_schema()

    @mcp.resource("session://schemas/steer")
    def steer_schema() -> dict[str, Any]:
        return SteerMessage.model_json_schema()

    @mcp.resource("session://docs/overview")
    def overview() -> str:
        return "Tenant-owned persistent sessions with exactly-once live steering."


__all__ = ["register"]
