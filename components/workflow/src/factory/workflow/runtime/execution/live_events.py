"""Canonical run-terminal live event projection."""
from __future__ import annotations

from typing import Any

from factory.workflow.runtime.event_emitter import emit as emit_workflow_event
from factory.workflow.runtime.graph_sync import workflow_entity_id


def emit_terminal(result: Any, run: Any, workflow: Any) -> None:
    if not result.done or result.status not in {"succeeded", "failed", "cancelled"}:
        return
    event_type = {
        "succeeded": "workflow.run_succeeded",
        "failed": "workflow.run_failed",
        "cancelled": "workflow.run_cancelled",
    }[result.status]
    payload = {
        "run_id": run.run_id, "entity_id": workflow_entity_id(run.run_id),
        "workflow_id": run.workflow_id, "workflow_type": workflow.name,
        "current_step_id": result.transition.get("step"),
        "status": result.status,
    }
    if result.error:
        from factory.mcp_utils.interface import sanitize_protected_error
        payload["error"] = sanitize_protected_error(result.error)
    emit_workflow_event(event_type, payload, run.model_dump(mode="json"))


__all__ = ["emit_terminal"]
