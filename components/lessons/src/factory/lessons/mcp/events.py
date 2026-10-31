"""Best-effort owner-derived lesson lifecycle Events projection."""
from __future__ import annotations

import asyncio
import hashlib
import logging
from typing import Any

from factory.mcp_utils.interface import (
    get_envelope, get_service, protected_canonical_json,
)

logger = logging.getLogger(__name__)


async def emit_lesson_event(
    lesson: Any, event_type: str, *, outcome: str | None = None,
) -> None:
    try:
        factory = get_service("tool_invoker_for_caller")
        invoke = factory("lessons") if callable(factory) else None
        if not callable(invoke):
            raise RuntimeError("Lessons Events MCP unavailable")
        envelope = {
            "tenant_id": lesson.tenant_id,
            "principal_id": lesson.owner_id,
        }
        payload = {
            "lesson_id": lesson.lesson_id, "status": lesson.status.value,
            "source": lesson.source.value, "scope": lesson.scope.value,
            "scope_id": lesson.scope_id or "", "revision": lesson.revision,
        }
        if outcome:
            payload["outcome"] = outcome
        raw = await asyncio.to_thread(
            invoke, {"brick_name": "events", "tool_name": "events_publish"},
            arguments={
                "event_type": event_type, "payload": payload,
                "source": "lessons", "tenant_id": lesson.tenant_id,
                "principal_id": lesson.owner_id,
            },
            idempotency_key=(
                f"lesson-event:{event_type}:{lesson.lesson_id}:{lesson.revision}"
            ), envelope=envelope,
        )
        structured = raw.get("result", {}).get("structured_content") if isinstance(raw, dict) else None
        if not isinstance(structured, dict) or structured.get("ok") is not True:
            raise RuntimeError("Lessons Events projection failed")
        await _emit_projection(invoke, lesson, event_type, envelope)
    except Exception as exc:
        logger.warning("lesson lifecycle event unavailable: %s", exc)


async def _emit_projection(invoke, lesson: Any, lifecycle_type: str, envelope: dict) -> None:
    ambient = get_envelope() or {}
    references = []
    source_ref = lesson.source_ref or ""
    if source_ref.startswith("kb:") and len(source_ref) > 3:
        references.append({
            "kind": "kb", "local_id": source_ref[3:],
            "entity_type": "KBDocument", "relation_type": "derived_from",
        })
    run_id = ambient.get("run_id")
    if isinstance(run_id, str) and run_id:
        references.append({
            "kind": "workflow-run", "local_id": run_id,
            "entity_type": "WorkflowRun", "relation_type": "learned_in",
        })
    references.extend({
        "kind": "lesson", "local_id": value,
        "entity_type": "Lesson", "relation_type": "supersedes",
    } for value in lesson.superseded_ids)
    record = {
        "source_system": "lessons",
        "action": "tombstone" if lifecycle_type == "lesson.removed" else "upsert",
        "subject_kind": "lesson", "subject_local_id": lesson.lesson_id,
        "subject_type": "Lesson", "source_digest": hashlib.sha256(
            protected_canonical_json({
                "lesson_id": lesson.lesson_id, "status": lesson.status.value,
                "source_ref": source_ref, "revision": lesson.revision,
                "references": references,
            })
        ).hexdigest(),
        "references": references,
    }
    digest = hashlib.sha256(protected_canonical_json(record)).hexdigest()
    binding = {
        "tenant_id": lesson.tenant_id, "owner_id": lesson.owner_id,
        "event_type": "graph.projection.requested",
        "subject_id": lesson.lesson_id, "revision": lesson.revision,
        "payload_digest": digest,
    }
    raw = await asyncio.to_thread(
        invoke, {"brick_name": "events", "tool_name": "events_publish_projection"},
        arguments={**binding, "record": record},
        idempotency_key=f"lesson-projection:{lesson.lesson_id}:{lesson.revision}",
        envelope=envelope, projection=binding,
    )
    structured = raw.get("result", {}).get("structured_content") if isinstance(raw, dict) else None
    if not isinstance(structured, dict) or structured.get("ok") is not True:
        raise RuntimeError("Lessons Graph projection failed")


__all__ = ["emit_lesson_event"]
