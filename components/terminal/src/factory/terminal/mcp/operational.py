"""Operational interactive terminal lifecycle tools."""
from __future__ import annotations

from typing import Any

from factory.mcp_utils.interface import ToolResult, fail, get_envelope, op_kind, operational
from factory.mcp_utils.registration import typed_tool

from .contracts import (
    MutationOutput, OpenInput, OutputChunk, ReadInput, ResizeInput,
    SessionInput, SessionOutput, WriteInput,
)
from ..runtime.models import TerminalSpawnSpec

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
    @operational(input_model=OpenInput, output_model=SessionOutput, idempotent=False)
    @op_kind("shell")
    async def terminal_open_session(
        shell: str | None = None, cwd: str | None = None,
        cols: int = 80, rows: int = 24,
    ) -> ToolResult[SessionOutput]:
        identity = _identity()
        if identity is None:
            return fail(_ERROR)
        try:
            session = await runtime.open_session(
                *identity, TerminalSpawnSpec(shell=shell, cwd=cwd, cols=cols, rows=rows))
            return SessionOutput(session=session)
        except Exception:
            return fail(_ERROR)

    @typed_tool(mcp)
    @operational(input_model=WriteInput, output_model=MutationOutput, idempotent=False)
    @op_kind("shell")
    async def terminal_write(session_id: str, data: str) -> ToolResult[MutationOutput]:
        identity = _identity()
        if identity is None:
            return fail(_ERROR)
        try:
            await runtime.write_input(*identity, session_id, data)
            return MutationOutput(session_id=session_id, ok=True)
        except Exception:
            return fail(_ERROR)

    @typed_tool(mcp)
    @operational(input_model=ReadInput, output_model=OutputChunk)
    async def terminal_read(
        session_id: str, timeout_seconds: float = 0.25,
    ) -> ToolResult[OutputChunk]:
        identity = _identity()
        if identity is None:
            return fail(_ERROR)
        try:
            chunk = await runtime.read_output(
                *identity, session_id, timeout_seconds=timeout_seconds)
            return OutputChunk(chunk=chunk)
        except Exception:
            return fail(_ERROR)

    @typed_tool(mcp)
    @operational(input_model=ResizeInput, output_model=SessionOutput)
    async def terminal_resize(
        session_id: str, cols: int, rows: int,
    ) -> ToolResult[SessionOutput]:
        identity = _identity()
        if identity is None:
            return fail(_ERROR)
        try:
            session = await runtime.resize(*identity, session_id, cols, rows)
            return SessionOutput(session=session)
        except Exception:
            return fail(_ERROR)

    @typed_tool(mcp)
    @operational(input_model=SessionInput, output_model=MutationOutput, idempotent=True)
    async def terminal_close(session_id: str) -> ToolResult[MutationOutput]:
        identity = _identity()
        if identity is None:
            return fail(_ERROR)
        try:
            closed = await runtime.close_session(*identity, session_id)
            return MutationOutput(session_id=session_id, ok=closed)
        except Exception:
            return fail(_ERROR)


__all__ = ["register"]
