"""Runtime port for owner-scoped interactive terminal sessions."""
from __future__ import annotations

from typing import Protocol

from .models import TerminalOutputChunk, TerminalSessionRef, TerminalSpawnSpec


class TerminalRuntimePort(Protocol):
    async def open_session(
        self, tenant_id: str, principal_id: str, spec: TerminalSpawnSpec,
    ) -> TerminalSessionRef: ...

    async def write_input(
        self, tenant_id: str, principal_id: str, session_id: str, data: str,
    ) -> None: ...

    async def read_output(
        self, tenant_id: str, principal_id: str, session_id: str,
        timeout_seconds: float = 0.25,
    ) -> TerminalOutputChunk: ...

    async def resize(
        self, tenant_id: str, principal_id: str, session_id: str,
        cols: int, rows: int,
    ) -> TerminalSessionRef: ...

    async def close_session(
        self, tenant_id: str, principal_id: str, session_id: str,
    ) -> bool: ...

    async def list_sessions(
        self, tenant_id: str, principal_id: str,
    ) -> list[TerminalSessionRef]: ...


__all__ = ["TerminalRuntimePort"]
