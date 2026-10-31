"""Authoritative active-Session project binding for Devtools MCP."""
from __future__ import annotations

import asyncio
import logging

from factory.mcp_utils.interface import get_envelope, get_service

from ..runtime.models import ProjectBinding

logger = logging.getLogger(__name__)


def identity_envelope(explicit: dict | None) -> dict:
    value = dict(explicit or {})
    value.update(get_envelope() or {})
    return value


async def project_binding(explicit: dict | None) -> ProjectBinding:
    envelope = identity_envelope(explicit)
    thread_id = envelope.get("thread_id") or envelope.get("session_id")
    if not isinstance(thread_id, str) or not thread_id:
        logger.error("devtools_project_binding_failed reason=missing_thread")
        raise ValueError("active Session thread is required")
    session_envelope = {
        key: value for key, value in envelope.items()
        if key != "thread_id" and value is not None
    }
    factory = get_service("tool_invoker_for_caller")
    invoke = factory("devtools") if callable(factory) else None
    if not callable(invoke):
        logger.error("devtools_project_binding_failed reason=service_unavailable")
        raise ValueError("Session project binding is unavailable")
    raw = await asyncio.to_thread(
        invoke, {"brick_name": "session", "tool_name": "resolve_thread"},
        arguments={"thread_id": thread_id, "envelope": session_envelope},
        idempotency_key=f"devtools-project:{thread_id}", envelope=session_envelope,
    )
    structured = raw.get("result", {}).get("structured_content") if isinstance(raw, dict) else None
    data = structured.get("data") if isinstance(structured, dict) and structured.get("ok") else None
    session = data.get("session") if isinstance(data, dict) else None
    if not isinstance(session, dict) or session.get("archived_at") is not None:
        error = structured.get("error") if isinstance(structured, dict) else None
        safe_error = error if error in {
            "session_identity_required", "session_not_found",
            "session_revision_conflict", "send_id_rejected",
        } else "unknown"
        logger.error(
            "devtools_project_binding_failed reason=session_unavailable error=%s",
            safe_error,
        )
        raise ValueError("active Session project binding is unavailable")
    project = session.get("project")
    if not isinstance(project, str) or not project:
        logger.error("devtools_project_binding_failed reason=project_unbound")
        raise ValueError("Session has no project binding")
    from factory.devtools.interface import validate_project
    root = validate_project(
        session["tenant_id"], session["owner_id"], session["session_id"], project,
    )
    return ProjectBinding(
        tenant_id=session["tenant_id"], owner_id=session["owner_id"],
        session_id=session["session_id"], root=root,
    )


__all__ = ["identity_envelope", "project_binding"]
