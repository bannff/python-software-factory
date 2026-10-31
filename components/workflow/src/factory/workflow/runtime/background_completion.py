"""Workflow-owned terminal projection into Session completion delivery."""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any

from factory.mcp_utils.interface import get_service, protected_canonical_json

_TERMINAL = {"succeeded": "ok", "failed": "failed", "cancelled": "stopped"}
_EVENT = "system.background_completion_recorded"


def record_background_completion(runtime: Any, run_id: str, envelope: Any) -> bool:
    record = runtime.storage.get_run(run_id=run_id)
    if record is None or record.status not in _TERMINAL or not _background(record):
        return False
    if any(event.event_type == _EVENT for event in runtime.storage.get_events_since(
        run_id=run_id, after_event_id=0,
    )):
        return False
    metadata = record.input["launch_metadata"]
    outcome = _TERMINAL[record.status]
    summary = _summary(record)
    digest = hashlib.sha256(protected_canonical_json({
        "outcome": outcome, "summary": summary,
    })).hexdigest()
    binding = {
        "tenant_id": str(record.tenant_id or ""),
        "owner_id": str(record.initiation_envelope.principal_id or ""),
        "session_id": str(metadata["origin_session_id"]),
        "run_id": record.run_id, "revision": 1, "result_digest": digest,
    }
    invoker_factory = get_service("tool_invoker_for_caller")
    invoker = invoker_factory("workflow") if callable(invoker_factory) else None
    if not callable(invoker):
        raise RuntimeError("workflow caller-bound tool invoker is unavailable")
    raw = invoker(
        {"brick_name": "session", "tool_name": "record_completion"},
        arguments={**binding, "outcome": outcome, "summary": summary},
        idempotency_key=f"background-completion:{run_id}",
        envelope=record.initiation_envelope.model_dump(mode="json"),
        completion=binding,
    )
    structured = raw.get("result", {}).get("structured_content") if isinstance(raw, dict) else None
    if not isinstance(structured, dict) or structured.get("ok") is not True:
        raise RuntimeError("origin completion delivery failed")
    runtime.storage.append_event(
        run_id=run_id, event_type=_EVENT,
        payload={"session_id": binding["session_id"], "result_digest": digest},
        envelope=envelope, now=datetime.now(timezone.utc),
    )
    from .projection_events import emit_run_projection
    emit_run_projection(
        tenant_id=binding["tenant_id"], owner_id=binding["owner_id"],
        run_id=record.run_id, session_id=binding["session_id"],
        revision=record.revision, status=record.status,
        envelope=record.initiation_envelope.model_dump(mode="json"),
    )
    return True


def _background(record: Any) -> bool:
    value = record.input.get("launch_metadata", {})
    return isinstance(value, dict) and value.get("kind") == "background_subagent"


def _summary(record: Any) -> str:
    if record.status == "succeeded":
        value = ((record.result or {}).get("task_result") or {}).get("result")
        if isinstance(value, dict) and isinstance(value.get("output"), str):
            return value["output"][:32_768] or "Background run completed."
        return "Background run completed."
    return (record.error or f"Background run {record.status}.")[:32_768]


__all__ = ["record_background_completion"]
