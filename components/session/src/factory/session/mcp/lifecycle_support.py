"""Uniform typed result mapping for session MCP tools."""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from factory.mcp_utils.interface import ToolResult, fail, ok

from ..runtime.errors import (
    SendIdRejectedError, SessionBindingRejectedError, SessionConflictError,
    SessionIdentityError, SessionNotFoundError, SessionProjectRejectedError,
)

_ERRORS = {
    SessionIdentityError: "session_identity_required",
    SessionNotFoundError: "session_not_found",
    SessionConflictError: "session_revision_conflict",
    SendIdRejectedError: "send_id_rejected",
    SessionBindingRejectedError: "session_binding_rejected",
    SessionProjectRejectedError: "session_project_path_refused",
}


def result(call: Callable[[], Any]) -> ToolResult[Any]:
    try:
        return ok(call())
    except tuple(_ERRORS) as exc:
        return fail(_ERRORS[type(exc)])


def identity(runtime: Any, explicit: dict[str, Any] | None) -> tuple[str, str]:
    """Prefer authenticated transport identity; explicit values may only match."""
    from factory.mcp_utils.interface import get_envelope
    from ..runtime.errors import SessionIdentityError

    ambient = get_envelope()
    if ambient is None:
        return runtime.identity(explicit)
    if explicit is not None and any(
        explicit.get(key) != ambient.get(key) for key in ("tenant_id", "principal_id")
    ):
        raise SessionIdentityError
    return runtime.identity(ambient)


__all__ = ["identity", "result"]
