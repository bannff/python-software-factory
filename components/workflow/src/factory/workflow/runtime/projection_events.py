"""Workflow-owned terminal relationship projection events."""
from __future__ import annotations

import hashlib
import logging
from typing import Any

from factory.mcp_utils.interface import get_service, protected_canonical_json

logger = logging.getLogger(__name__)


def emit_run_projection(
    *, tenant_id: str, owner_id: str, run_id: str,
    session_id: str, revision: int, status: str,
    envelope: dict[str, Any],
) -> None:
    factory = get_service("tool_invoker_for_caller")
    invoke = factory("workflow") if callable(factory) else None
    if not callable(invoke):
        logger.warning("Workflow Graph projection skipped: Events unavailable")
        return
    references = [{
        "kind": "session", "local_id": session_id,
        "entity_type": "Session", "relation_type": "about_run",
    }]
    record = {
        "source_system": "workflow", "action": "upsert",
        "subject_kind": "workflow-run", "subject_local_id": run_id,
        "subject_type": "WorkflowRun", "source_digest": hashlib.sha256(
            protected_canonical_json({
                "run_id": run_id, "session_id": session_id,
                "revision": revision, "status": status,
            })
        ).hexdigest(), "references": references,
    }
    digest = hashlib.sha256(protected_canonical_json(record)).hexdigest()
    binding = {
        "tenant_id": tenant_id, "owner_id": owner_id,
        "event_type": "graph.projection.requested", "subject_id": run_id,
        "revision": revision, "payload_digest": digest,
    }
    raw = invoke(
        {"brick_name": "events", "tool_name": "events_publish_projection"},
        arguments={**binding, "record": record},
        idempotency_key=f"workflow-projection:{run_id}:{revision}",
        envelope=envelope, projection=binding,
    )
    structured = raw.get("result", {}).get("structured_content") if isinstance(raw, dict) else None
    if not isinstance(structured, dict) or structured.get("ok") is not True:
        logger.warning("Workflow Graph projection failed")


__all__ = ["emit_run_projection"]
