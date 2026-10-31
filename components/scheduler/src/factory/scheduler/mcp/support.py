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
    ambient = get_envelope()
    value = ambient if ambient is not None else explicit
    thread = value.get("thread_id") or value.get("session_id")
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
        return fail(str(exc) if str(exc).startswith("scheduler_") else "schedule_invalid")


__all__ = ["identity", "owner_identity", "result"]
