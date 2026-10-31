"""Strict typed MCP tools for owner-scoped Agent Crews.

Authority is ambient (envelope-derived); tools never accept raw
``tenant_id``/``owner_id``. All failures collapse to a fixed safe-error enum
so nothing about existence, revision, or storage internals leaks beyond the
typed outcome. Delete is authoring-gated; the rest are deterministic reads or
operational owner-scoped CAS mutations.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable, TYPE_CHECKING

from factory.mcp_utils.interface import (
    ToolResult, authoring, deterministic, fail, get_envelope, ok, operational,
)

from ..runtime.crew_contracts import (
    CrewConflictError, CrewExistsError, CrewIdentityError,
    CrewModelUnresolvedError, CrewNotFoundError,
)
from ..runtime.crew_lifecycle import CrewLifecycle
from .contracts.crews import (
    CrewCreateInput, CrewDefaultInput, CrewDeleteInput, CrewDeletedOutput,
    CrewIdInput, CrewListInput, CrewOutput, CrewRecordDTO, CrewResolveInput,
    CrewResolvedOutput, CrewsOutput, CrewUpdateInput,
)

if TYPE_CHECKING:
    from ..agent import SuperAgent

logger = logging.getLogger(__name__)


def _lifecycle(agent: "SuperAgent") -> CrewLifecycle:
    store = getattr(agent, "crew_store", None)
    if store is None:
        from ..runtime.adapters.crew_store_disk import DiskCrewStore
        store = DiskCrewStore(Path(agent.config_dir) / "crews")
        agent.crew_store = store
    return CrewLifecycle(store)


def _run(fn: Callable[[str, str], Any]) -> ToolResult[Any]:
    """Resolve ambient identity, run ``fn``, map every failure to a safe enum."""
    try:
        tenant_id, owner_id = CrewLifecycle.identity(get_envelope())
    except CrewIdentityError:
        return fail("crew_identity_required")
    try:
        return ok(fn(tenant_id, owner_id))
    except CrewExistsError:
        return fail("crew_exists")
    except CrewNotFoundError:
        return fail("crew_not_found")
    except CrewConflictError:
        return fail("crew_revision_conflict")
    except CrewModelUnresolvedError:
        return fail("crew_model_unresolved")
    except (ValueError, OSError, PermissionError) as exc:
        logger.warning(
            "Crew operation unavailable error_type=%s", type(exc).__name__,
        )
        return fail("crew_unavailable")


def _record(crew: Any) -> CrewRecordDTO:
    return CrewRecordDTO.model_validate(crew.model_dump())


def register(mcp: Any, agent: "SuperAgent") -> None:
    """Register Crew list/get/resolve/create/update/default/delete tools."""

    @mcp.tool()
    @deterministic(input_model=CrewListInput, output_model=CrewsOutput)
    def agent_list_crews() -> ToolResult[CrewsOutput]:
        """List the caller's owner-scoped Crews and default pointer."""
        def run(tenant_id: str, owner_id: str) -> CrewsOutput:
            lifecycle = _lifecycle(agent)
            crews = lifecycle.list(tenant_id, owner_id)
            return CrewsOutput(
                count=len(crews), crews=[_record(crew) for crew in crews],
                default_id=lifecycle.default_id(tenant_id, owner_id),
            )
        return _run(run)

    @mcp.tool()
    @deterministic(input_model=CrewIdInput, output_model=CrewOutput)
    def agent_get_crew(crew_id: str) -> ToolResult[CrewOutput]:
        """Get one owner-scoped Crew; absence is a safe not-found."""
        def run(tenant_id: str, owner_id: str) -> CrewOutput:
            crew = _lifecycle(agent).get(tenant_id, owner_id, crew_id)
            if crew is None:
                raise CrewNotFoundError(crew_id)
            return CrewOutput(crew=_record(crew))
        return _run(run)

    @mcp.tool()
    @deterministic(input_model=CrewResolveInput, output_model=CrewResolvedOutput)
    def agent_resolve_crew(crew_id: str, session_model: str = "") -> ToolResult[CrewResolvedOutput]:
        """Resolve persona/model/project/scope for Session to materialize."""
        def run(tenant_id: str, owner_id: str) -> CrewResolvedOutput:
            resolved = _lifecycle(agent).resolve(
                tenant_id, owner_id, crew_id, session_model,
            )
            return CrewResolvedOutput(
                crew_id=resolved.crew_id, persona_id=resolved.persona_id,
                model_id=resolved.model_id, project=resolved.project,
                workspace=resolved.workspace, memory_scope=resolved.memory_scope,
            )
        return _run(run)

    @mcp.tool()
    @operational(input_model=CrewCreateInput, output_model=CrewOutput)
    def agent_create_crew(
        crew_id: str, name: str, persona_id: str, project: str, memory_scope: str,
        description: str = "", workspace: str = "", model: str = "",
        triggers: list[str] | None = None,
    ) -> ToolResult[CrewOutput]:
        """Exclusively create an owner-scoped Crew at revision 1."""
        def run(tenant_id: str, owner_id: str) -> CrewOutput:
            crew = _lifecycle(agent).create(
                tenant_id, owner_id, crew_id=crew_id, name=name,
                persona_id=persona_id, project=project, memory_scope=memory_scope,
                description=description, workspace=workspace, model=model,
                triggers=triggers,
            )
            return CrewOutput(crew=_record(crew))
        return _run(run)

    @mcp.tool()
    @operational(input_model=CrewUpdateInput, output_model=CrewOutput)
    def agent_update_crew(
        crew_id: str, name: str, persona_id: str, project: str, memory_scope: str,
        expected_revision: int, description: str = "", workspace: str = "",
        model: str = "", triggers: list[str] | None = None,
    ) -> ToolResult[CrewOutput]:
        """Revision-fenced update of an owner-scoped Crew."""
        def run(tenant_id: str, owner_id: str) -> CrewOutput:
            crew = _lifecycle(agent).update(
                tenant_id, owner_id, crew_id=crew_id, name=name,
                persona_id=persona_id, project=project, memory_scope=memory_scope,
                expected_revision=expected_revision, description=description,
                workspace=workspace, model=model, triggers=triggers,
            )
            return CrewOutput(crew=_record(crew))
        return _run(run)

    @mcp.tool()
    @operational(input_model=CrewDefaultInput, output_model=CrewOutput)
    def agent_set_default_crew(crew_id: str, expected_revision: int) -> ToolResult[CrewOutput]:
        """Fenced set of the owner's default Crew to an existing revision."""
        def run(tenant_id: str, owner_id: str) -> CrewOutput:
            lifecycle = _lifecycle(agent)
            lifecycle.set_default(tenant_id, owner_id, crew_id, expected_revision)
            crew = lifecycle.get(tenant_id, owner_id, crew_id)
            if crew is None:
                raise CrewNotFoundError(crew_id)
            return CrewOutput(crew=_record(crew))
        return _run(run)

    @mcp.tool()
    @authoring(input_model=CrewDeleteInput, output_model=CrewDeletedOutput)
    def agent_delete_crew(crew_id: str, expected_revision: int) -> ToolResult[CrewDeletedOutput]:
        """Authoring-gated fenced delete; clears the default if it matched."""
        def run(tenant_id: str, owner_id: str) -> CrewDeletedOutput:
            _lifecycle(agent).delete(tenant_id, owner_id, crew_id, expected_revision)
            return CrewDeletedOutput(crew_id=crew_id, deleted=True)
        return _run(run)


__all__ = ["register"]
