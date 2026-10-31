"""Workflow-owned durable run cancellation lifecycle."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .authority import execution_envelope
from .envelope import Envelope
from .graph_sync import sync_run
from .event_emitter import emit as emit_workflow_event
from .execution_cancellation import signal_execution_cancellation
from .ports import DurableWorkflowStorage, ToolInvokerPort, WorkflowStorage
from .run_cas import ACTIVE_STATUSES, observe_or_transition


def cancel_run(
    *, storage: WorkflowStorage, durable: DurableWorkflowStorage | None,
    invoker: ToolInvokerPort | None, run_id: str, reason: str | None,
    envelope: Envelope,
) -> dict[str, Any]:
    """Win durable cancellation before best-effort same-process signaling."""
    record = storage.get_run(run_id=run_id)
    if record is None:
        from .operations import WorkflowError
        raise WorkflowError("Run not found")
    execution_envelope(record, envelope)
    if record.status not in ACTIVE_STATUSES:
        return {"ok": True, "status": record.status}
    message = reason or "cancelled"
    updated, won = observe_or_transition(
        storage, record, status="cancelled",
        fields=lambda current: {
            "current_step_id": current.current_step_id,
            "waiting_for_event_type": None, "last_event_id": None,
            "result": current.result, "error": current.error or message,
        },
    )
    if not won:
        return {"ok": True, "status": updated.status}
    cancellation: dict[str, Any] | None = None
    if durable and updated.workflow_version_id:
        attempts = durable.cancel_task_attempts(
            run_id=run_id, reason=message,
        )
        cancellation = signal_execution_cancellation(
            durable=durable, invoker=invoker, record=updated,
            attempts=attempts,
            envelope=execution_envelope(updated, envelope),
        )
    storage.append_event(
        run_id=run_id, event_type="system.run_cancelled",
        payload={"reason": reason, "cancellation": cancellation},
        envelope=envelope, now=datetime.now(timezone.utc),
    )
    sync_run(updated.model_dump(mode="json"), envelope.model_dump(mode="json"))
    emit_workflow_event(
        "workflow.run_cancelled",
        {"run_id": run_id, "status": "cancelled", "reason": message,
         "cancellation": cancellation},
        updated.model_dump(mode="json"),
    )
    return {"ok": True, "status": "cancelled", "cancellation": cancellation}
