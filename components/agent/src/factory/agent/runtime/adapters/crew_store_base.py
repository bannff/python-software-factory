"""Shared owner-locked CAS logic for Crew stores.

Both the in-memory and disk adapters inherit the identical revision-fenced
create/update/delete/default contract from ``_CrewStoreBase`` and supply
only the storage primitives. Local mutating operations run under a
per-authority re-entrant lock keyed by a fixed-width hash of the validated
``(tenant_id, owner_id)`` so same-process writers serialize and the default
pointer cannot dangle. The local adapter is single-process; any distributed
adapter MUST provide storage-native conditional-write fencing.
"""
from __future__ import annotations

import hashlib
import threading

from ..crew_contracts import (
    CrewConfig, CrewConflictError, CrewExistsError, CrewNotFoundError,
)

_LOCKS: dict[str, threading.RLock] = {}
_REGISTRY_LOCK = threading.Lock()


def authority_hash(tenant_id: str, owner_id: str) -> str:
    """Fixed-width hash of the authority pair (no raw owner text on disk)."""
    return hashlib.sha256(f"{tenant_id}\x00{owner_id}".encode()).hexdigest()


def _owner_lock(key: str) -> threading.RLock:
    with _REGISTRY_LOCK:
        lock = _LOCKS.get(key)
        if lock is None:
            lock = threading.RLock()
            _LOCKS[key] = lock
        return lock


class _CrewStoreBase:
    """Revision-fenced CAS over storage primitives supplied by subclasses."""

    # --- storage primitives (subclass responsibility) ---
    def _load(self, tenant_id: str, owner_id: str) -> dict[str, CrewConfig]:
        raise NotImplementedError

    def _store(self, config: CrewConfig) -> None:
        raise NotImplementedError

    def _remove(self, tenant_id: str, owner_id: str, crew_id: str) -> None:
        raise NotImplementedError

    def _load_default(self, tenant_id: str, owner_id: str) -> str | None:
        raise NotImplementedError

    def _store_default(
        self, tenant_id: str, owner_id: str, crew_id: str | None,
    ) -> None:
        raise NotImplementedError

    # --- public CAS contract ---
    def list_crews(self, tenant_id: str, owner_id: str) -> list[CrewConfig]:
        with _owner_lock(authority_hash(tenant_id, owner_id)):
            return list(self._load(tenant_id, owner_id).values())

    def get_crew(
        self, tenant_id: str, owner_id: str, crew_id: str,
    ) -> CrewConfig | None:
        with _owner_lock(authority_hash(tenant_id, owner_id)):
            return self._load(tenant_id, owner_id).get(crew_id)

    def create_crew(self, config: CrewConfig) -> CrewConfig:
        with _owner_lock(authority_hash(config.tenant_id, config.owner_id)):
            crews = self._load(config.tenant_id, config.owner_id)
            if config.id in crews:
                raise CrewExistsError(config.id)
            created = config.model_copy(update={"revision": 1})
            self._store(created)
            return created

    def update_crew(
        self, config: CrewConfig, expected_revision: int,
    ) -> CrewConfig:
        with _owner_lock(authority_hash(config.tenant_id, config.owner_id)):
            current = self._load(config.tenant_id, config.owner_id).get(config.id)
            if current is None:
                raise CrewNotFoundError(config.id)
            if current.revision != expected_revision:
                raise CrewConflictError(config.id)
            updated = config.model_copy(update={"revision": current.revision + 1})
            self._store(updated)
            return updated

    def delete_crew(
        self, tenant_id: str, owner_id: str, crew_id: str, expected_revision: int,
    ) -> None:
        with _owner_lock(authority_hash(tenant_id, owner_id)):
            current = self._load(tenant_id, owner_id).get(crew_id)
            if current is None:
                raise CrewNotFoundError(crew_id)
            if current.revision != expected_revision:
                raise CrewConflictError(crew_id)
            self._remove(tenant_id, owner_id, crew_id)
            if self._load_default(tenant_id, owner_id) == crew_id:
                self._store_default(tenant_id, owner_id, None)

    def get_default(self, tenant_id: str, owner_id: str) -> str | None:
        with _owner_lock(authority_hash(tenant_id, owner_id)):
            return self._load_default(tenant_id, owner_id)

    def set_default(
        self, tenant_id: str, owner_id: str, crew_id: str, expected_revision: int,
    ) -> None:
        with _owner_lock(authority_hash(tenant_id, owner_id)):
            current = self._load(tenant_id, owner_id).get(crew_id)
            if current is None:
                raise CrewNotFoundError(crew_id)
            if current.revision != expected_revision:
                raise CrewConflictError(crew_id)
            self._store_default(tenant_id, owner_id, crew_id)


__all__ = ["_CrewStoreBase", "authority_hash"]
