"""Deterministic terminal session and shell discovery tools."""
from __future__ import annotations

from typing import Any

from factory.mcp_utils.interface import ToolResult, deterministic, fail, get_envelope
from factory.mcp_utils.registration import typed_tool

from .contracts import EmptyInput, SessionsOutput, ShellsOutput

_ERROR = "terminal_unavailable"


def _identity() -> tuple[str, str] | None:
    envelope = get_envelope() or {}
    tenant = envelope.get("tenant_id")
    principal = envelope.get("principal_id")
    if not isinstance(tenant, str) or not tenant.strip() \
            or not isinstance(principal, str) or not principal.strip():
        return None
    return tenant, principal


def register(mcp: Any, runtime: Any) -> None:
    @typed_tool(mcp)
    @deterministic(input_model=EmptyInput, output_model=SessionsOutput)
    async def terminal_list() -> ToolResult[SessionsOutput]:
        identity = _identity()
        if identity is None:
            return fail(_ERROR)
        sessions = await runtime.list_sessions(*identity)
        return SessionsOutput(sessions=sessions)

    @typed_tool(mcp)
    @deterministic(input_model=EmptyInput, output_model=ShellsOutput)
    def terminal_list_shells() -> ToolResult[ShellsOutput]:
        return ShellsOutput(shells=runtime.list_shells())


__all__ = ["register"]
