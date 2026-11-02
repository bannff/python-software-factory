"""Existence check for the Crew a Session is bound to.

The Session brick stores ``crew_id`` as an opaque reference; without this
check a ghost id was accepted and failed later. Crews live in the agent brick,
so the check goes through the caller-bound tool invoker (never an import of the
agent runtime). With no invoker mounted (a standalone Session deployment) the
reference stays opaque, as before.
"""
from __future__ import annotations

from uuid import uuid4

from factory.mcp_utils.interface import get_service

from ..runtime.errors import SessionCrewNotFoundError


def verify_crew(tenant_id: str, owner_id: str, crew_id: str) -> None:
    if not crew_id:
        return
    factory = get_service("tool_invoker_for_caller")
    invoke = factory("session") if callable(factory) else None
    if not callable(invoke):
        return
    raw = invoke(
        {"brick_name": "agent", "tool_name": "agent_get_crew"},
        arguments={"crew_id": crew_id},
        # Fresh key: a replayed "not found" must not outlive the crew's creation.
        idempotency_key=f"session-crew:{crew_id}:{uuid4().hex}",
        envelope={"tenant_id": tenant_id, "principal_id": owner_id},
    )
    structured = raw.get("result", {}).get("structured_content") if isinstance(raw, dict) else None
    if isinstance(structured, dict) and structured.get("error") == "crew_not_found":
        raise SessionCrewNotFoundError(crew_id)


__all__ = ["verify_crew"]
