"""Notification inbox MCP ambient identity and content-free failure mapping.

Tenant/owner are derived *solely* from the ambient request envelope with
strict :class:`Identity` validation — never from tool input. Foreign and
absent notifications collapse to one opaque ``not_found``; stale CAS and a
drifted mark-all count are distinct fixed conflicts; every other failure is a
single content-free code that never carries storage detail.
"""
from __future__ import annotations

from typing import Any, Callable

from pydantic import TypeAdapter, ValidationError

from factory.mcp_utils.interface import ToolResult, fail, get_envelope, ok

from ..runtime.inbox_models import (
    NotificationNotFoundError, RevisionConflictError, UnreadCountConflictError,
)
from ..runtime.inbox_targets import Identity

_IDENTITY = TypeAdapter(Identity)
_ERROR = "notification_inbox_unavailable"


def inbox_authority() -> tuple[str, str]:
    """Return ``(tenant_id, owner_id)`` from the ambient envelope, or raise."""
    envelope = get_envelope()
    if not isinstance(envelope, dict):
        raise ValueError(_ERROR)
    try:
        return (
            _IDENTITY.validate_python(envelope.get("tenant_id"), strict=True),
            _IDENTITY.validate_python(envelope.get("principal_id"), strict=True),
        )
    except ValidationError as exc:
        raise ValueError(_ERROR) from exc


def inbox_result(build: Callable[[str, str], Any]) -> ToolResult[Any]:
    """Derive identity, run ``build(tenant, owner)``, map failures to fixed codes."""
    try:
        return ok(build(*inbox_authority()))
    except NotificationNotFoundError:
        return fail("notification_not_found")
    except RevisionConflictError:
        return fail("notification_revision_conflict")
    except UnreadCountConflictError:
        return fail("notification_unread_count_conflict")
    except Exception:  # noqa: BLE001 — fixed safe, content-free boundary
        return fail(_ERROR)


__all__ = ["_ERROR", "inbox_authority", "inbox_result"]
