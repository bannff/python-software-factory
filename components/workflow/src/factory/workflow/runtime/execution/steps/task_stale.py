"""Observe the authoritative task attempt after a stale CAS fence."""
from __future__ import annotations

from factory.workflow.runtime.models import RunRecord, StepDefinition, WorkflowDefinition
from factory.workflow.runtime.ports import DurableWorkflowStorage, WorkflowStorage
from .base import StepResult
from .task_completion import success, terminal
from .task_observer import attempt_after_stale_fence


def observe_stale(
    durable: DurableWorkflowStorage, storage: WorkflowStorage,
    workflow: WorkflowDefinition, run: RunRecord, step: StepDefinition,
    attempt_id: str, error: ValueError, expected: str,
) -> StepResult:
    attempt = attempt_after_stale_fence(
        durable, run_id=run.run_id, attempt_id=attempt_id,
        error=error, expected=expected,
    )
    status = attempt.get("status")
    authoritative_id = str(attempt.get("attempt_id") or attempt_id)
    transition = {"step": step.id, "attempt_id": authoritative_id}
    if status in {"pending", "running"}:
        return StepResult(
            True, None, {**transition, "status": "running"},
            status="running", effect_owned=False,
        )
    if status == "continued":
        return StepResult(
            False, step.id, {**transition, "status": "continuing"},
            effect_owned=False,
        )
    if status == "succeeded":
        output = durable.load_verified_step(run=run, step_id=step.id).output
        return success(
            storage, durable, workflow, run, step, authoritative_id, output,
            effect_owned=False,
        )
    if status == "failed" and attempt.get("retry_approved"):
        return StepResult(
            False, step.id, {**transition, "status": "retrying"},
            effect_owned=False,
        )
    if status in {"failed", "cancelled"}:
        result = terminal(
            storage, run, step, status,
            str(attempt.get("error") or f"task {status}"),
        )
        result.transition["attempt_id"] = authoritative_id
        return result
    raise RuntimeError(f"unsupported fenced attempt status: {status}")


__all__ = ["observe_stale"]
