"""Handler for wait_for_event steps."""

from __future__ import annotations

from datetime import datetime, timezone

from factory.workflow.runtime.envelope import Envelope
from factory.workflow.runtime.models import StepDefinition, RunRecord
from factory.workflow.runtime.ports import WorkflowStorage
from .base import StepResult


def handle_wait_for_event(
    step: StepDefinition,
    run: RunRecord,
    storage: WorkflowStorage,
    envelope: Envelope,
    last_event_id: int,
) -> tuple[StepResult, int]:
    """Handle wait_for_event step - check for matching event."""
    now = datetime.now(timezone.utc)
    expected = step.event_type or ""
    events = storage.get_events_since(run_id=run.run_id, after_event_id=last_event_id)
    
    match = None
    for ev in events:
        last_event_id = max(last_event_id, ev.id)
        if ev.event_type == expected:
            match = ev
            break
    
    if match is None:
        storage.update_run(
            run_id=run.run_id,
            status="waiting",
            current_step_id=step.id,
            waiting_for_event_type=expected,
            last_event_id=last_event_id,
            result=run.result,
            error=run.error,
            now=now,
            expected_statuses={"pending", "running", "waiting"},
            expected_revision=run.revision,
        )
        return StepResult(
            done=True,
            next_step_id=None,
            transition={"step": step.id, "status": "waiting", "waiting_for": expected},
            status="waiting",
        ), last_event_id
    
    next_step = step.next
    if next_step is None:
        storage.update_run(
            run_id=run.run_id,
            status="succeeded",
            current_step_id=step.id,
            waiting_for_event_type=None,
            last_event_id=match.id,
            result={"ok": True, "event": match.payload},
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
            result={"ok": True, "event": match.payload},
        ), match.id
    
    return StepResult(
        done=False,
        next_step_id=next_step,
        transition={"from": step.id, "to": next_step, "consumed_event": match.event_type},
    ), last_event_id
