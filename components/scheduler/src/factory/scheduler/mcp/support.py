"""Scheduler MCP identity and failure mapping."""
from __future__ import annotations

from typing import Any, Callable

from factory.mcp_utils.interface import ToolResult, fail, get_envelope, ok

from ..runtime.errors import ScheduleConflictError, ScheduleNotFoundError


def owner_identity(explicit: dict[str, Any] | None) -> tuple[str, str]:
    """Resolve ambient owner authority for page reads and CAS actions."""
    ambient = get_envelope()
    value = ambient if ambient is not None else explicit
    if not isinstance(value, dict):
        raise ValueError("scheduler_identity_required")
    tenant, owner = value.get("tenant_id"), value.get("principal_id")
    if not all(isinstance(item, str) and item for item in (tenant, owner)):
        raise ValueError("scheduler_identity_required")
    return tenant, owner


def identity(explicit: dict[str, Any] | None) -> tuple[str, str, str]:
    """Resolve owner plus active thread for schedule creation."""
    tenant, owner = owner_identity(explicit)
    # Authority (tenant/owner) is ambient-only; the active thread is context a
    # UI caller supplies, so it may come from the explicit envelope even when
    # an ambient one carries the principal.
    thread = next((
        value.get(key) for value in (get_envelope(), explicit)
        if isinstance(value, dict) for key in ("thread_id", "session_id")
        if value.get(key)
    ), None)
    if not isinstance(thread, str) or not thread:
        raise ValueError("scheduler_identity_required")
    return tenant, owner, thread


def result(call: Callable[[], Any]) -> ToolResult[Any]:
    try:
        return ok(call())
    except ScheduleNotFoundError:
        return fail("schedule_not_found")
    except ScheduleConflictError:
        return fail("schedule_revision_conflict")
    except ValueError as exc:
        return failure_code(exc)


def failure_code(exc: ValueError) -> ToolResult[Any]:
    """Typed code for a ValueError: ``scheduler_*`` codes pass through."""
    return fail(str(exc) if str(exc).startswith("scheduler_") else "schedule_invalid")


__all__ = ["failure_code", "identity", "owner_identity", "result"]
