"""Run-terminal projection for durable named-MCP steps."""
from __future__ import annotations

from typing import Any

from factory.mcp_utils.interface import sanitize_protected_error
from factory.workflow.runtime.models import (
    RunRecord, StepDefinition, WorkflowDefinition,
)
from factory.workflow.runtime.ports import DurableWorkflowStorage, WorkflowStorage
from factory.workflow.runtime.run_binding import (
    DurableIntegrityError, verify_durable_run_binding,
)
from factory.workflow.runtime.run_cas import observe_or_transition
from factory.workflow.runtime.task_refs import resolve_refs
from .base import StepResult


def terminal(
    storage: WorkflowStorage, run: RunRecord, step: StepDefinition,
    status: str, error: str | None = None,
    result: dict[str, Any] | None = None,
) -> StepResult:
    safe_error = sanitize_protected_error(error) if error is not None else None
    updated, won = observe_or_transition(
        storage, run, status=status,
        fields=lambda current: {
            "current_step_id": step.id, "waiting_for_event_type": None,
            "last_event_id": None,
            "result": result if result is not None else current.result,
            "error": safe_error,
        },
    )
    return StepResult(
        True, None,
        {"step": updated.current_step_id or step.id, "status": updated.status},
        updated.status, updated.result, updated.error, won,
    )


def _project(
    workflow: WorkflowDefinition, run: RunRecord,
    durable: DurableWorkflowStorage, final_output: Any,
) -> Any:
    verify_durable_run_binding(run)
    if workflow.result_projection is None:
        return final_output
    cache: dict[str, Any] = {}

    def verified(step_id: str) -> Any:
        if step_id not in cache:
            cache[step_id] = durable.load_verified_step(run=run, step_id=step_id)
        return cache[step_id]

    return resolve_refs(
        workflow.result_projection,
        lambda step_id: verified(step_id).output,
        run_input=run.input,
        load_evidence=lambda step_id: verified(step_id).evidence,
    )


def success(
    storage: WorkflowStorage, durable: DurableWorkflowStorage,
    workflow: WorkflowDefinition, run: RunRecord, step: StepDefinition,
    attempt_id: str, output: Any, *, effect_owned: bool,
) -> StepResult:
    transition = {"step": step.id, "status": "succeeded", "attempt_id": attempt_id}
    if step.next is not None:
        transition.update({"from": step.id, "to": step.next})
        return StepResult(False, step.next, transition, effect_owned=effect_owned)
    try:
        projected = _project(workflow, run, durable, output)
    except DurableIntegrityError:
        raise
    except Exception as exc:
        result = terminal(
            storage, run, step, "failed",
            sanitize_protected_error(
                f"terminal projection failed: {type(exc).__name__}: {exc}"
            ),
        )
    else:
        result = terminal(
            storage, run, step, "succeeded",
            result={"ok": True, "task_result": projected},
        )
    result.transition["attempt_id"] = attempt_id
    return result
