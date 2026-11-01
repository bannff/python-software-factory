"""Connections runtime: registry operations plus gateway mount lifecycle."""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable

from .models import ServerRecord, ServerSpec, ServersDocument, validate_name
from .mount import brick_name, build_catalog, open_source
from .ports import ServerStore

logger = logging.getLogger(__name__)


Mount = Callable[[str, Any], Any]
Unmount = Callable[[str], Any]


def _root_cause(exc: BaseException) -> BaseException:
    while isinstance(exc, BaseExceptionGroup) and exc.exceptions:
        exc = exc.exceptions[0]
    return exc


def _reason(exc: BaseException) -> str:
    """Allowlisted diagnostic: root-cause type, plus the OS reason for OSErrors.

    Arbitrary exception text can echo resolved env/header credentials, so it is
    never forwarded.
    """
    cause = _root_cause(exc)
    if isinstance(cause, OSError) and cause.strerror:
        return f"{type(cause).__name__}: {cause.strerror}"
    return type(cause).__name__


ErrorKey = tuple[str, str, str]


class ConnectionsRuntime:
    """One process-wide runtime; the API base injects the gateway mount seam."""

    def __init__(self, store: ServerStore) -> None:
        self.store = store
        self._register: Mount | None = None
        self._unregister: Unmount | None = None
        self._sources: dict[str, Any] = {}
        self._tool_counts: dict[str, int] = {}
        self._tool_names: dict[str, tuple[str, ...]] = {}
        self._mount_errors: dict[ErrorKey, str] = {}
        self._lock = asyncio.Lock()

    def attach_gateway(self, register: Mount, unregister: Unmount) -> None:
        """Receive the gateway's pseudo-brick mount seam (bases own composition)."""
        self._register, self._unregister = register, unregister

    # -- registry -----------------------------------------------------------
    def list(self, tenant_id: str, owner_id: str) -> tuple[ServerRecord, ...]:
        return self.store.list(tenant_id, owner_id)

    def add(self, tenant_id: str, owner_id: str, name: str, spec: ServerSpec) -> ServerRecord:
        return self.store.upsert(tenant_id, owner_id, validate_name(name), spec, None)

    def import_document(
        self, tenant_id: str, owner_id: str, document: ServersDocument,
    ) -> tuple[ServerRecord, ...]:
        """Add every server in a pasted mcpServers document; existing names are replaced."""
        records = []
        for name, spec in document.mcpServers.items():
            current = self.store.get(tenant_id, owner_id, name)
            records.append(self.store.upsert(
                tenant_id, owner_id, name, spec, current.revision if current else None,
            ))
        return tuple(records)

    def update(
        self, tenant_id: str, owner_id: str, name: str, spec: ServerSpec, expected_revision: int,
    ) -> ServerRecord:
        return self.store.upsert(tenant_id, owner_id, validate_name(name), spec, expected_revision)

    def remove(self, tenant_id: str, owner_id: str, name: str, expected_revision: int) -> bool:
        removed = self.store.remove(tenant_id, owner_id, validate_name(name), expected_revision)
        return removed

    # -- mount --------------------------------------------------------------
    async def mount(self, record: ServerRecord) -> int:
        """Dial one server and register it as a pseudo-brick; returns tool count."""
        key = (record.tenant_id, record.owner_id, record.name)
        async with self._lock:
            self._mount_errors.pop(key, None)
            await self._unmount_locked(record.name)
            source: Any = None
            try:
                source, tools = await open_source(record)
                catalog = build_catalog(record, source, tools)
                self._sources[record.name] = source
                self._tool_counts[record.name] = len(catalog.tool_map())
                self._tool_names[record.name] = tuple(sorted(catalog.tool_map()))
                if self._register is not None:
                    self._register(brick_name(record.name), catalog)
            except Exception as exc:
                # Registration succeeds regardless, so the view needs the cause.
                self._mount_errors[key] = _reason(exc)
                await self._unmount_locked(record.name)
                if source is not None:
                    await self._close(source, record.name)
                raise
            return len(catalog.tool_map())

    async def unmount(self, name: str, owner: tuple[str, str] | None = None) -> None:
        """Drop a mount; ``owner`` also clears that owner's retained mount error."""
        async with self._lock:
            if owner is not None:
                self._mount_errors.pop((*owner, name), None)
            await self._unmount_locked(name)

    @staticmethod
    async def _close(source: Any, name: str) -> None:
        try:
            await source.close()
        except Exception:  # noqa: BLE001 - teardown is best-effort
            logger.debug("connections: close failed for %s", name, exc_info=True)

    async def _unmount_locked(self, name: str) -> None:
        source = self._sources.pop(name, None)
        self._tool_counts.pop(name, None)
        self._tool_names.pop(name, None)
        if source is not None:
            await self._close(source, name)
        if self._unregister is not None:
            self._unregister(brick_name(name))

    async def reload(self, tenant_id: str, owner_id: str) -> dict[str, int | str]:
        """Re-discover this owner's enabled servers; disabled ones are unmounted."""
        return await self._remount(self.store.list(tenant_id, owner_id))

    async def remount_all(self) -> dict[str, int | str]:
        """Startup: mount every enabled server across owners (mounts are process-wide)."""
        return await self._remount(self.store.list_all())

    async def _remount(self, records: tuple[ServerRecord, ...]) -> dict[str, int | str]:
        outcome: dict[str, int | str] = {}
        for record in records:
            if not record.spec.enabled:
                await self.unmount(record.name, (record.tenant_id, record.owner_id))
                outcome[record.name] = "disabled"
                continue
            try:
                outcome[record.name] = await self.mount(record)
            except Exception as exc:  # noqa: BLE001 - one bad server must not block others
                logger.warning("connections: mount failed for %s: %s", record.name, type(exc).__name__)
                outcome[record.name] = f"error:{type(exc).__name__}"
        return outcome

    def mounted(self) -> tuple[str, ...]:
        return tuple(sorted(self._sources))

    def tool_count(self, name: str) -> int:
        return self._tool_counts.get(name, 0)

    def mount_error(self, tenant_id: str, owner_id: str, name: str) -> str | None:
        return self._mount_errors.get((tenant_id, owner_id, name))

    def tool_names(self, name: str) -> tuple[str, ...]:
        return self._tool_names.get(name, ())


_RUNTIME: ConnectionsRuntime | None = None


def get_runtime() -> ConnectionsRuntime:
    global _RUNTIME
    if _RUNTIME is None:
        import os
        from .adapters.server_store_sqlite import SqliteServerStore
        _RUNTIME = ConnectionsRuntime(SqliteServerStore(os.getenv(
            "COMPANION_X_CONNECTIONS_DB_PATH", "./.storage/connections.db",
        )))
    return _RUNTIME


def set_runtime(runtime: ConnectionsRuntime | None) -> None:
    global _RUNTIME
    _RUNTIME = runtime


__all__ = ["ConnectionsRuntime", "get_runtime", "set_runtime"]
