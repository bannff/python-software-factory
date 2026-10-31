"""Ambient identity and Session verification for Lessons MCP."""
from __future__ import annotations

import asyncio
from typing import Any

from factory.mcp_utils.interface import get_envelope, get_service


def owner_authority(explicit: dict[str, Any] | None) -> tuple[str, str, dict[str, Any]]:
    """Resolve ambient owner authority while preserving supplied session context."""
    ambient = get_envelope()
    supplied = dict(explicit or {})
    if isinstance(ambient, dict) and ambient:
        context = {**supplied, **{key: value for key, value in ambient.items()
                                  if value is not None}}
    else:
        context = supplied
    tenant, owner = context.get("tenant_id"), context.get("principal_id")
    if not all(isinstance(item, str) and item for item in (tenant, owner)):
        raise ValueError("lesson_owner_context_required")
    return tenant, owner, context


def authority(explicit: dict[str, Any] | None) -> tuple[str, str, str, dict[str, Any]]:
    """Resolve owner plus active thread for lesson creation."""
    tenant, owner, context = owner_authority(explicit)
    thread = context.get("session_id") or context.get("thread_id")
    if not isinstance(thread, str) or not thread:
        raise ValueError("lesson_owner_context_required")
    return tenant, owner, thread, context


async def verify_session(thread_id: str, context: dict[str, Any]) -> None:
    factory = get_service("tool_invoker_for_caller")
    invoke = factory("lessons") if callable(factory) else None
    if not callable(invoke):
        raise ValueError("lesson_session_unavailable")
    raw = await asyncio.to_thread(
        invoke, {"brick_name": "session", "tool_name": "resolve_thread"},
        arguments={"thread_id": thread_id, "envelope": context},
        idempotency_key=f"lessons-session:{thread_id}", envelope=context,
    )
    structured = raw.get("result", {}).get("structured_content") if isinstance(raw, dict) else None
    data = structured.get("data") if isinstance(structured, dict) and structured.get("ok") else None
    session = data.get("session") if isinstance(data, dict) else None
    if not isinstance(session, dict):
        raise ValueError("lesson_session_not_found")
    if session.get("state") != "active":
        raise ValueError("lesson_session_restricted")


__all__ = ["authority", "owner_authority", "verify_session"]
