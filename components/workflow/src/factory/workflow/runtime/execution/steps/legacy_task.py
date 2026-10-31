"""Compatibility handler for local, Celery, and Dagster task executors."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from factory.workflow.runtime.envelope import Envelope
from factory.workflow.runtime.models import RunRecord, StepDefinition
from factory.workflow.runtime.ports import WorkflowStorage
from ..adapters import TaskExecutor, TaskStatus
from .base import StepResult


def handle_legacy_task(
    step: StepDefinition, run: RunRecord, storage: WorkflowStorage,
    envelope: Envelope, executor: TaskExecutor,
) -> StepResult:
    """Preserve the pre-named-MCP executor path and task options."""
    now = datetime.now(timezone.utc)
    task_id = f"{run.run_id}:{step.id}:{uuid.uuid4().hex[:8]}"
    result = executor.submit(
        task_id=task_id, task_type=step.task_type or "default",
        payload={**run.input, **step.task_payload}, options=step.task_options,
    )
    if result.status == TaskStatus.SUCCEEDED:
        if step.next is not None:
            return StepResult(
                False, step.next,
                {"from": step.id, "to": step.next, "task_id": task_id},
            )
        value = {"ok": True, "task_result": result.result}
        updated = storage.update_run(
            run_id=run.run_id, status="succeeded", current_step_id=step.id,
            waiting_for_event_type=None, last_event_id=None, result=value,
            error=None, now=now, expected_statuses={"pending", "running", "waiting"},
            expected_revision=run.revision,
        )
        status = updated.status
        return StepResult(
            True, None, {"step": step.id, "status": status, "task_id": task_id},
            status=status, result=value if status == "succeeded" else updated.result,
        )
    if result.status == TaskStatus.FAILED:
        error = result.error or "Task failed"
        updated = storage.update_run(
            run_id=run.run_id, status="failed", current_step_id=step.id,
            waiting_for_event_type=None, last_event_id=None, result=run.result,
            error=error, now=now, expected_statuses={"pending", "running", "waiting"},
            expected_revision=run.revision,
        )
        return StepResult(
            True, None, {"step": step.id, "status": updated.status, "task_id": task_id},
            status=updated.status, error=error,
        )
    updated = storage.update_run(
        run_id=run.run_id, status="running", current_step_id=step.id,
        waiting_for_event_type=f"task:{task_id}", last_event_id=None,
        result=run.result, error=run.error, now=now,
        expected_statuses={"pending", "running", "waiting"},
        expected_revision=run.revision,
    )
    return StepResult(
        True, None, {"step": step.id, "status": updated.status, "task_id": task_id},
        status=updated.status,
    )
