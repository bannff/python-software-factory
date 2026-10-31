"""Ports for the connections brick (external MCP server registry and mount)."""
from __future__ import annotations

from typing import Any, Protocol

from .models import ServerRecord, ServerSpec


class ServerStore(Protocol):
    """Owner-scoped durable registry keyed by ``(tenant_id, owner_id, name)``."""

    def list(self, tenant_id: str, owner_id: str) -> tuple[ServerRecord, ...]: ...

    def list_all(self) -> tuple[ServerRecord, ...]: ...

    def get(self, tenant_id: str, owner_id: str, name: str) -> ServerRecord | None: ...

    def upsert(
        self, tenant_id: str, owner_id: str, name: str, spec: ServerSpec,
        expected_revision: int | None,
    ) -> ServerRecord:
        """Create when ``expected_revision`` is None; otherwise CAS update."""
        ...

    def remove(
        self, tenant_id: str, owner_id: str, name: str, expected_revision: int,
    ) -> bool: ...


class ToolSource(Protocol):
    """A dialled external MCP server exposing a scoped list/call surface."""

    async def list_capabilities(self) -> tuple[Any, ...]: ...

    async def invoke(self, request: Any) -> Any: ...

    async def close(self) -> None: ...


__all__ = ["ServerStore", "ToolSource"]
