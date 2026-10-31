"""Canonical live events for durable named-task attempts."""
from __future__ import annotations

from typing import Any

from factory.mcp_utils.interface import protected_error_text
from factory.workflow.runtime.event_emitter import emit as emit_workflow_event


def started(run: Any, step: Any, claim: Any) -> None:
    payload = {
        "run_id": run.run_id, "workflow_id": run.workflow_id,
        "step_id": step.id, "attempt_id": claim.attempt_id,
        "revision": claim.revision, "attempt_number": claim.attempt_number,
        "status": "running",
    }
    metadata = run.input.get("launch_metadata", {})
    if isinstance(metadata, dict) and metadata.get("kind") == "background_subagent":
        payload["agent_id"] = str(metadata.get("persona_id") or step.id)
    emit_workflow_event(
        "workflow.attempt_started", payload,
        run.model_dump(mode="json"),
    )


def completed(
    run: Any, step: Any, claim: Any, *, status: str,
    error: str | None = None, protected: bool = False,
) -> None:
    payload = {
        "run_id": run.run_id, "workflow_id": run.workflow_id,
        "step_id": step.id, "attempt_id": claim.attempt_id,
        "revision": claim.revision, "attempt_number": claim.attempt_number,
        "status": status,
    }
    metadata = run.input.get("launch_metadata", {})
    if isinstance(metadata, dict) and metadata.get("kind") == "background_subagent":
        payload["agent_id"] = str(metadata.get("persona_id") or step.id)
    if error is not None:
        payload["error"] = protected_error_text(error, protected=protected)
    emit_workflow_event(
        "workflow.attempt_completed", payload, run.model_dump(mode="json"),
    )


__all__ = ["completed", "started"]
