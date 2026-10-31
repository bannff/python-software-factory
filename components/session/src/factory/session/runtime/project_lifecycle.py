"""Validated Session project, model, and crew-rebind lifecycle mixin."""
from __future__ import annotations

from typing import Any

from pydantic import TypeAdapter, ValidationError

from .errors import SessionBindingRejectedError, SessionProjectRejectedError
from .models import CrewRef, Identifier, MemoryScope, SessionRecord

_CREW = TypeAdapter(CrewRef)
_SCOPE = TypeAdapter(MemoryScope)
_AGENT = TypeAdapter(Identifier)


def _validated_project(tenant_id: str, owner_id: str, session_id: str, project: str) -> str:
    """Translate devtools' ``PathRefused`` into the session brick's own
    error type (found live 2026-09-16, row 17 cycle: this previously
    propagated uncaught, flattening to a generic ``tool_execution_failed``
    at the MCP boundary and hiding the real cause)."""
    from factory.devtools.interface import validate_project
    from factory.devtools.runtime.path_resolver import PathRefused
    try:
        return validate_project(tenant_id, owner_id, session_id, project)
    except PathRefused as exc:
        raise SessionProjectRejectedError from exc


def _validated_model(model: str) -> str:
    """Reject empty/unresolvable models through the gateway before persistence."""
    candidate = model.strip()
    if not candidate:
        raise SessionBindingRejectedError
    from factory.llm_gateway.interface import resolve_chat_profile
    try:
        resolve_chat_profile(candidate)
    except ValueError as exc:
        raise SessionBindingRejectedError from exc
    return candidate


def _validated_binding(
    crew_id: str, memory_scope: str, agent_id: str,
) -> tuple[str, str, str]:
    try:
        return (
            _CREW.validate_python(crew_id), _SCOPE.validate_python(memory_scope),
            _AGENT.validate_python(agent_id),
        )
    except ValidationError as exc:
        raise SessionBindingRejectedError from exc


class ProjectLifecycleMixin:
    store: Any

    def bind_project(
        self, tenant_id: str, owner_id: str, session_id: str,
        project: str, expected_revision: int,
    ) -> SessionRecord:
        record = self._require_active(tenant_id, owner_id, session_id)
        canonical = _validated_project(tenant_id, owner_id, session_id, project)
        value = self.store.set_project(
            tenant_id, owner_id, session_id, canonical, expected_revision,
        )
        return self._session_result(value, tenant_id, owner_id, record.session_id)

    def set_model(
        self, tenant_id: str, owner_id: str, session_id: str,
        model: str, expected_revision: int,
    ) -> SessionRecord:
        self._require_active(tenant_id, owner_id, session_id)
        value = self.store.set_model(
            tenant_id, owner_id, session_id, _validated_model(model), expected_revision,
        )
        return self._session_result(value, tenant_id, owner_id, session_id)

    def rebind(
        self, tenant_id: str, owner_id: str, session_id: str, crew_id: str,
        memory_scope: str, agent_id: str, model: str, expected_revision: int,
        *, project: str | None = None, workspace: str | None = None,
    ) -> SessionRecord:
        current = self._require_active(tenant_id, owner_id, session_id)
        crew, scope, persona = _validated_binding(crew_id, memory_scope, agent_id)
        canonical = current.project
        if project is not None:
            canonical = _validated_project(tenant_id, owner_id, session_id, project)
        value = self.store.rebind(
            tenant_id, owner_id, session_id, crew, scope, persona,
            _validated_model(model), canonical,
            current.workspace if workspace is None else workspace,
            expected_revision,
        )
        return self._session_result(value, tenant_id, owner_id, session_id)


__all__ = ["ProjectLifecycleMixin"]
