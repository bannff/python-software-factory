"""In-memory Crew store — tests and the AgentCore-adapter reference shape."""
from __future__ import annotations

from ..crew_contracts import CrewConfig
from .crew_store_base import _CrewStoreBase, authority_hash


class InMemoryCrewStore(_CrewStoreBase):
    """Process-local owner-partitioned Crew store with the CAS contract."""

    def __init__(self) -> None:
        self._crews: dict[str, dict[str, CrewConfig]] = {}
        self._defaults: dict[str, str] = {}

    def _load(self, tenant_id: str, owner_id: str) -> dict[str, CrewConfig]:
        return dict(self._crews.get(authority_hash(tenant_id, owner_id), {}))

    def _store(self, config: CrewConfig) -> None:
        key = authority_hash(config.tenant_id, config.owner_id)
        self._crews.setdefault(key, {})[config.id] = config

    def _remove(self, tenant_id: str, owner_id: str, crew_id: str) -> None:
        self._crews.get(authority_hash(tenant_id, owner_id), {}).pop(crew_id, None)

    def _load_default(self, tenant_id: str, owner_id: str) -> str | None:
        return self._defaults.get(authority_hash(tenant_id, owner_id))

    def _store_default(
        self, tenant_id: str, owner_id: str, crew_id: str | None,
    ) -> None:
        key = authority_hash(tenant_id, owner_id)
        if crew_id is None:
            self._defaults.pop(key, None)
        else:
            self._defaults[key] = crew_id


__all__ = ["InMemoryCrewStore"]
