"""Owner-scoped supervised PTY session registry."""
from __future__ import annotations

import asyncio
import os
import time
import uuid
from pathlib import Path

from .models import TerminalOutputChunk, TerminalSessionRef, TerminalSpawnSpec
from .pty_session import PtySession, spawn_pty
from .shell_resolver import resolve_shell

MAX_SESSIONS = 12
ORPHAN_TIMEOUT_SECONDS = 900.0


class TerminalSessionUnavailable(ValueError):
    pass


class SessionRegistry:
    def __init__(self) -> None:
        self._sessions: dict[str, PtySession] = {}
        self._lock = asyncio.Lock()

    async def open(
        self, tenant_id: str, principal_id: str, spec: TerminalSpawnSpec,
    ) -> TerminalSessionRef:
        async with self._lock:
            owned = sum(
                session.tenant_id == tenant_id
                and session.principal_id == principal_id
                for session in self._sessions.values()
            )
            if owned >= MAX_SESSIONS:
                raise TerminalSessionUnavailable("terminal session unavailable")
            session_id = f"term_{uuid.uuid4().hex}"
            shell = resolve_shell(spec.shell)
            cwd = spec.cwd or os.getcwd()
            session = await spawn_pty(
                session_id, tenant_id, principal_id, shell, cwd,
                spec.cols, spec.rows,
            )
            self._sessions[session_id] = session
            return _ref(session)

    async def write(
        self, tenant_id: str, principal_id: str, session_id: str, data: str,
    ) -> None:
        await self.write_bytes(
            tenant_id, principal_id, session_id, data.encode())

    async def write_bytes(
        self, tenant_id: str, principal_id: str, session_id: str, data: bytes,
    ) -> None:
        session = self._get(tenant_id, principal_id, session_id)
        assert session is not None
        await session.write(data)

    async def read(
        self, tenant_id: str, principal_id: str, session_id: str, timeout: float,
    ) -> TerminalOutputChunk:
        data, alive = await self.read_bytes(
            tenant_id, principal_id, session_id, timeout)
        return TerminalOutputChunk(
            session_id=session_id,
            data=data.decode("utf-8", errors="replace"), eof=not alive)

    async def read_bytes(
        self, tenant_id: str, principal_id: str, session_id: str, timeout: float,
    ) -> tuple[bytes, bool]:
        session = self._get(tenant_id, principal_id, session_id)
        assert session is not None
        return await session.read(timeout), session.alive

    async def resize(
        self, tenant_id: str, principal_id: str, session_id: str,
        cols: int, rows: int,
    ) -> TerminalSessionRef:
        session = self._get(tenant_id, principal_id, session_id)
        session.resize(cols, rows)
        return _ref(session)

    async def close(
        self, tenant_id: str, principal_id: str, session_id: str,
    ) -> bool:
        session = self._get(tenant_id, principal_id, session_id, missing_ok=True)
        if session is None:
            return False
        async with self._lock:
            self._sessions.pop(session_id, None)
        await session.close()
        return True

    def list(self, tenant_id: str, principal_id: str) -> list[TerminalSessionRef]:
        return [
            _ref(session) for session in self._sessions.values()
            if session.tenant_id == tenant_id and session.principal_id == principal_id
        ]

    async def current_cwd(
        self, tenant_id: str, principal_id: str, session_id: str,
    ) -> str:
        session = self._get(tenant_id, principal_id, session_id)
        assert session is not None
        return await session.current_cwd()

    async def reap_orphans(self, now: float | None = None) -> int:
        cutoff = (now if now is not None else time.monotonic()) - ORPHAN_TIMEOUT_SECONDS
        victims = [
            session for session in self._sessions.values()
            if not session.alive or (
                session.disconnected_at is not None and session.disconnected_at < cutoff)
        ]
        for session in victims:
            await self.close(session.tenant_id, session.principal_id, session.session_id)
        return len(victims)

    async def close_all(self) -> int:
        sessions = tuple(self._sessions.values())
        for session in sessions:
            await self.close(session.tenant_id, session.principal_id, session.session_id)
        return len(sessions)

    def mark_connected(
        self, tenant_id: str, principal_id: str, session_id: str,
    ) -> tuple[TerminalSessionRef, bytes, int]:
        session = self._get(tenant_id, principal_id, session_id)
        assert session is not None
        if not session.alive:
            raise TerminalSessionUnavailable("terminal session unavailable")
        session.connection_epoch += 1
        session.disconnected_at = None
        return _ref(session), session.scrollback(), session.connection_epoch

    def session_ids(self) -> frozenset[str]:
        return frozenset(self._sessions)

    def connection_is_current(
        self, tenant_id: str, principal_id: str, session_id: str, epoch: int,
    ) -> bool:
        session = self._get(
            tenant_id, principal_id, session_id, missing_ok=True)
        return session is not None and session.connection_epoch == epoch

    def mark_disconnected(
        self, tenant_id: str, principal_id: str, session_id: str, epoch: int,
    ) -> bool:
        session = self._get(
            tenant_id, principal_id, session_id, missing_ok=True)
        if session is None or session.connection_epoch != epoch:
            return False
        session.disconnected_at = time.monotonic()
        return True

    def _get(
        self, tenant_id: str, principal_id: str, session_id: str,
        missing_ok: bool = False,
    ) -> PtySession | None:
        session = self._sessions.get(session_id)
        if session is None or session.tenant_id != tenant_id \
                or session.principal_id != principal_id:
            if missing_ok:
                return None
            raise TerminalSessionUnavailable("terminal session unavailable")
        return session


def _ref(session: PtySession) -> TerminalSessionRef:
    return TerminalSessionRef(
        session_id=session.session_id, shell=session.shell, cwd=session.cwd,
        cols=session.cols, rows=session.rows, alive=session.alive,
    )


__all__ = [
    "MAX_SESSIONS", "ORPHAN_TIMEOUT_SECONDS", "SessionRegistry",
    "TerminalSessionUnavailable",
]
