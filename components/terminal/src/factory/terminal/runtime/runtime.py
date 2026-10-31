"""Terminal runtime facade."""
from __future__ import annotations

import asyncio

from .models import (
    TerminalCompletionResult, TerminalCompletionSpec, TerminalOutputChunk,
    TerminalSessionRef, TerminalSpawnSpec,
)
from .session_registry import SessionRegistry
from .shell_resolver import list_available_shells


class TerminalRuntime:
    def __init__(self, registry: SessionRegistry | None = None) -> None:
        self.registry = registry or SessionRegistry()

    async def open_session(
        self, tenant_id: str, principal_id: str, spec: TerminalSpawnSpec,
    ) -> TerminalSessionRef:
        return await self.registry.open(tenant_id, principal_id, spec)

    async def write_input(
        self, tenant_id: str, principal_id: str, session_id: str, data: str,
    ) -> None:
        await self.registry.write(tenant_id, principal_id, session_id, data)

    async def write_bytes(
        self, tenant_id: str, principal_id: str, session_id: str, data: bytes,
    ) -> None:
        await self.registry.write_bytes(
            tenant_id, principal_id, session_id, data)

    async def read_output(
        self, tenant_id: str, principal_id: str, session_id: str,
        timeout_seconds: float = 0.25,
    ) -> TerminalOutputChunk:
        return await self.registry.read(
            tenant_id, principal_id, session_id, timeout_seconds)

    async def resize(
        self, tenant_id: str, principal_id: str, session_id: str,
        cols: int, rows: int,
    ) -> TerminalSessionRef:
        return await self.registry.resize(
            tenant_id, principal_id, session_id, cols, rows)

    async def read_bytes(
        self, tenant_id: str, principal_id: str, session_id: str,
        timeout_seconds: float = 0.25,
    ) -> tuple[bytes, bool]:
        return await self.registry.read_bytes(
            tenant_id, principal_id, session_id, timeout_seconds)

    async def complete(
        self, tenant_id: str, principal_id: str, spec: TerminalCompletionSpec,
    ) -> TerminalCompletionResult:
        """Complete against the authenticated live session's current cwd."""
        cwd = await self.registry.current_cwd(
            tenant_id, principal_id, spec.session_id)
        if spec.argv is not None:
            from .command_completion import complete_commands
            return await asyncio.to_thread(
                complete_commands, spec.argv, spec.token, cwd)
        from .completion import complete_paths
        return await asyncio.to_thread(
            complete_paths, cwd, spec.token, spec.folders_only)

    def active_session_ids(self) -> frozenset[str]:
        return self.registry.session_ids()

    async def close_session(
        self, tenant_id: str, principal_id: str, session_id: str,
    ) -> bool:
        return await self.registry.close(tenant_id, principal_id, session_id)

    async def list_sessions(
        self, tenant_id: str, principal_id: str,
    ) -> list[TerminalSessionRef]:
        return self.registry.list(tenant_id, principal_id)

    def list_shells(self) -> list[str]:
        return list_available_shells()

    def connect_session(
        self, tenant_id: str, principal_id: str, session_id: str,
    ) -> tuple[TerminalSessionRef, bytes, int]:
        """Attach an authenticated transport and return replay plus epoch."""
        return self.registry.mark_connected(tenant_id, principal_id, session_id)

    def connection_is_current(
        self, tenant_id: str, principal_id: str, session_id: str, epoch: int,
    ) -> bool:
        return self.registry.connection_is_current(
            tenant_id, principal_id, session_id, epoch)

    def disconnect_session(
        self, tenant_id: str, principal_id: str, session_id: str, epoch: int,
    ) -> bool:
        """Mark disconnected only if this transport still owns the epoch."""
        return self.registry.mark_disconnected(
            tenant_id, principal_id, session_id, epoch)

    async def close(self) -> int:
        """Terminate every live PTY owned by this runtime."""
        return await self.registry.close_all()


_runtime: TerminalRuntime | None = None


def get_runtime() -> TerminalRuntime:
    global _runtime
    if _runtime is None:
        _runtime = TerminalRuntime()
    return _runtime


def reset_runtime() -> None:
    global _runtime
    _runtime = None


__all__ = ["TerminalRuntime", "get_runtime", "reset_runtime"]
