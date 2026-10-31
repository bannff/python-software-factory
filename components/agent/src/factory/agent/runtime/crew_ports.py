"""Focused owner-scoped ``CrewStore`` port.

This is deliberately NOT the persona ``RegistryStore`` widened — a Crew
has a different identity model (every method is authority-scoped, there
is no global list/get fallback) and a fenced default pointer the persona
store never had. Disk and in-memory adapters implement this same CAS
contract; an AgentCore-backed adapter slots in later behind it.

Semantics:
- ``create_crew`` is exclusive: a duplicate id raises ``CrewExistsError``.
- ``update_crew`` / ``delete_crew`` / ``set_default`` compare
  ``expected_revision`` under an owner lock and raise ``CrewConflictError``
  on mismatch; a missing target raises ``CrewNotFoundError``.
- The default pointer can never dangle: deleting the current default
  clears it in the same fenced operation, and ``set_default`` refuses a
  crew that does not exist for the owner.
"""
from __future__ import annotations

from typing import Protocol

from .crew_contracts import CrewConfig


class CrewStore(Protocol):
    """Persistence for owner-scoped Crew definitions (DATA tier)."""

    def list_crews(self, tenant_id: str, owner_id: str) -> list[CrewConfig]:
        """Return every Crew owned by ``(tenant_id, owner_id)``."""
        ...

    def get_crew(
        self, tenant_id: str, owner_id: str, crew_id: str,
    ) -> CrewConfig | None:
        """Return one owner-scoped Crew, or ``None`` if absent."""
        ...

    def create_crew(self, config: CrewConfig) -> CrewConfig:
        """Exclusively create a Crew; duplicate id raises ``CrewExistsError``."""
        ...

    def update_crew(
        self, config: CrewConfig, expected_revision: int,
    ) -> CrewConfig:
        """Revision-fenced replace; returns the persisted next revision."""
        ...

    def delete_crew(
        self, tenant_id: str, owner_id: str, crew_id: str, expected_revision: int,
    ) -> None:
        """Revision-fenced delete; clears the default pointer if it matched."""
        ...

    def get_default(self, tenant_id: str, owner_id: str) -> str | None:
        """Return the owner's default Crew id, or ``None``."""
        ...

    def set_default(
        self, tenant_id: str, owner_id: str, crew_id: str, expected_revision: int,
    ) -> None:
        """Fenced set of the default pointer to an existing, current Crew."""
        ...


__all__ = ["CrewStore"]
