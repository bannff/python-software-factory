"""Owner-scoped Crew lifecycle and resolution over a ``CrewStore``.

Identity is ambient-derived from the authenticated envelope — raw
``tenant_id``/``owner_id`` are never accepted from client input. Resolution
reuses the existing persona resolver and Devtools' public ``validate_project``
(no reimplementation) and applies the fixed effective-model precedence with a
non-empty final guard so an unresolved model can never yield an invalid Crew.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from pydantic import TypeAdapter, ValidationError

from .crew_contracts import (
    CrewConfig, CrewIdentityError, CrewModelUnresolvedError, Identity,
)
from .crew_ports import CrewStore
from .personas import resolve_agent_config

_IDENTITY = TypeAdapter(Identity)
_CHAT_MODEL_ENV = "COMPANION_X_CHAT_MODEL"


@dataclass(frozen=True)
class ResolvedCrew:
    """Materialized fields Session consumes to start or resume a run."""

    crew_id: str
    persona_id: str
    model_id: str
    project: str
    workspace: str
    memory_scope: str


class CrewLifecycle:
    """Business behavior over the owner-scoped ``CrewStore`` port."""

    def __init__(self, store: CrewStore) -> None:
        self.store = store

    @staticmethod
    def identity(envelope: dict[str, Any] | None) -> tuple[str, str]:
        """Prefer authenticated transport identity; reject absent/malformed."""
        if not isinstance(envelope, dict):
            raise CrewIdentityError
        try:
            tenant_id = _IDENTITY.validate_python(envelope.get("tenant_id"))
            owner_id = _IDENTITY.validate_python(envelope.get("principal_id"))
        except ValidationError as exc:
            raise CrewIdentityError from exc
        return tenant_id, owner_id

    def list(self, tenant_id: str, owner_id: str) -> list[CrewConfig]:
        return self.store.list_crews(tenant_id, owner_id)

    def get(self, tenant_id: str, owner_id: str, crew_id: str) -> CrewConfig | None:
        return self.store.get_crew(tenant_id, owner_id, crew_id)

    def default_id(self, tenant_id: str, owner_id: str) -> str | None:
        return self.store.get_default(tenant_id, owner_id)

    def create(
        self, tenant_id: str, owner_id: str, *, crew_id: str, name: str,
        persona_id: str, project: str, memory_scope: str, description: str = "",
        workspace: str = "", model: str = "", triggers: list[str] | None = None,
    ) -> CrewConfig:
        canonical = self._validate_project(tenant_id, owner_id, crew_id, project)
        self._validate_definition(persona_id, model)
        config = CrewConfig(
            tenant_id=tenant_id, owner_id=owner_id, id=crew_id, name=name,
            description=description, persona_id=persona_id, project=canonical,
            workspace=workspace, memory_scope=memory_scope, model=model,
            triggers=list(triggers or []), revision=1,
        )
        return self.store.create_crew(config)

    def update(
        self, tenant_id: str, owner_id: str, *, crew_id: str, name: str,
        persona_id: str, project: str, memory_scope: str, expected_revision: int,
        description: str = "", workspace: str = "", model: str = "",
        triggers: list[str] | None = None,
    ) -> CrewConfig:
        canonical = self._validate_project(tenant_id, owner_id, crew_id, project)
        self._validate_definition(persona_id, model)
        config = CrewConfig(
            tenant_id=tenant_id, owner_id=owner_id, id=crew_id, name=name,
            description=description, persona_id=persona_id, project=canonical,
            workspace=workspace, memory_scope=memory_scope, model=model,
            triggers=list(triggers or []), revision=expected_revision,
        )
        return self.store.update_crew(config, expected_revision)

    def delete(
        self, tenant_id: str, owner_id: str, crew_id: str, expected_revision: int,
    ) -> None:
        self.store.delete_crew(tenant_id, owner_id, crew_id, expected_revision)

    def set_default(
        self, tenant_id: str, owner_id: str, crew_id: str, expected_revision: int,
    ) -> None:
        self.store.set_default(tenant_id, owner_id, crew_id, expected_revision)

    def resolve(
        self, tenant_id: str, owner_id: str, crew_id: str,
        session_model: str = "",
    ) -> ResolvedCrew:
        """Resolve a Crew to materialized fields for Session to persist."""
        from .crew_contracts import CrewNotFoundError

        crew = self.store.get_crew(tenant_id, owner_id, crew_id)
        if crew is None:
            raise CrewNotFoundError(crew_id)
        persona = resolve_agent_config(crew.persona_id)
        model_id = _effective_model(session_model, crew.model, getattr(persona, "model", ""))
        self._validate_model(model_id)
        return ResolvedCrew(
            crew_id=crew.id, persona_id=crew.persona_id, model_id=model_id,
            project=crew.project, workspace=crew.workspace,
            memory_scope=crew.memory_scope,
        )

    @staticmethod
    def _validate_definition(persona_id: str, model: str) -> None:
        resolve_agent_config(persona_id)
        if model:
            CrewLifecycle._validate_model(model)

    @staticmethod
    def _validate_model(model: str) -> None:
        from factory.llm_gateway.interface import resolve_chat_profile
        try:
            resolve_chat_profile(model)
        except ValueError as exc:
            raise CrewModelUnresolvedError("crew model unavailable") from exc

    @staticmethod
    def _validate_project(
        tenant_id: str, owner_id: str, crew_id: str, project: str,
    ) -> str:
        from factory.devtools.interface import validate_project

        return validate_project(tenant_id, owner_id, crew_id, project)


def _effective_model(session_model: str, crew_model: str, persona_model: str) -> str:
    """Fixed precedence: Session → Crew → persona → env; empty is a failure."""
    for candidate in (session_model, crew_model, persona_model,
                      os.getenv(_CHAT_MODEL_ENV, "")):
        chosen = (candidate or "").strip()
        if chosen:
            return chosen
    raise CrewModelUnresolvedError("no non-empty effective model")


__all__ = ["CrewLifecycle", "ResolvedCrew"]
