"""Handler for noop steps."""

from __future__ import annotations

from datetime import datetime, timezone

from factory.workflow.runtime.envelope import Envelope
from factory.workflow.runtime.models import StepDefinition, RunRecord
from factory.workflow.runtime.ports import WorkflowStorage
from .base import StepResult


def handle_noop(
    step: StepDefinition,
    run: RunRecord,
    storage: WorkflowStorage,
    envelope: Envelope,
) -> StepResult:
    """Handle noop step - just transition to next."""
    now = datetime.now(timezone.utc)
    next_step = step.next
    
    if next_step is None:
        storage.update_run(
            run_id=run.run_id,
            status="succeeded",
            current_step_id=step.id,
            waiting_for_event_type=None,
            last_event_id=None,
            result={"ok": True},
            error=None,
            now=now,
            expected_statuses={"pending", "running", "waiting"},
            expected_revision=run.revision,
        )
        storage.append_event(
            run_id=run.run_id,
            event_type="system.transition",
            payload={"to_status": "succeeded", "step": step.id},
            envelope=envelope,
            now=now,
        )
        return StepResult(
            done=True,
            next_step_id=None,
            transition={"step": step.id, "status": "succeeded"},
            status="succeeded",
            result={"ok": True},
        )
    
    return StepResult(
        done=False,
        next_step_id=next_step,
        transition={"from": step.id, "to": next_step},
    )
