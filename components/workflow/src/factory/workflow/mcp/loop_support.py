"""Identity and origin helpers for Workflow loop MCP tools."""
from __future__ import annotations

import asyncio
from typing import Any

from factory.mcp_utils.interface import get_envelope, get_service

from ..runtime.envelope import Envelope, parse_envelope


def authority(explicit: dict[str, Any] | None) -> Envelope:
    ambient = get_envelope()
    if isinstance(ambient, dict) and ambient:
        supplied = explicit if isinstance(explicit, dict) else {}
        value = {
            **supplied,
            **{key: item for key, item in ambient.items() if item is not None},
        }
    else:
        value = explicit
    envelope = parse_envelope(value)
    if not envelope.tenant_id or not envelope.principal_id:
        raise ValueError("loop_owner_context_required")
    return envelope


async def resolve_origin(envelope: Envelope) -> str:
    factory = get_service("tool_invoker_for_caller")
    invoke = factory("workflow") if callable(factory) else None
    if not callable(invoke):
        raise ValueError("loop_origin_unavailable")
    context = envelope.model_dump(mode="json")
    raw = await asyncio.to_thread(
        invoke, {"brick_name": "session", "tool_name": "resolve_thread"},
        arguments={"thread_id": envelope.session_id, "envelope": context},
        idempotency_key=f"workflow-loop-origin:{envelope.session_id}",
        envelope=context,
    )
    structured = raw.get("result", {}).get("structured_content") if isinstance(raw, dict) else None
    data = structured.get("data") if isinstance(structured, dict) and structured.get("ok") else None
    session = data.get("session") if isinstance(data, dict) else None
    session_id = session.get("session_id") if isinstance(session, dict) else None
    if not isinstance(session_id, str) or not session_id:
        raise ValueError("loop_origin_not_found")
    return session_id


__all__ = ["authority", "resolve_origin"]
