"""Deterministic named-task input reconstruction from frozen authority."""
from __future__ import annotations

from typing import Any, Callable

from .models import RunRecord, StepDefinition, WorkflowDefinition
from .task_models import VerifiedStepResult
from .task_refs import resolve_refs


def resolve_task_input(
    workflow: WorkflowDefinition, step: StepDefinition, run: RunRecord,
    load_step: Callable[[str], VerifiedStepResult],
) -> dict[str, Any]:
    """Resolve one exact base argument object from frozen workflow material."""
    declared = (
        {**run.input, **step.task_payload}
        if workflow.schema_version == "v1" else step.task_payload
    )
    cache: dict[str, VerifiedStepResult] = {}

    def verified(step_id: str) -> VerifiedStepResult:
        if step_id not in cache:
            cache[step_id] = load_step(step_id)
        return cache[step_id]

    resolved = resolve_refs(
        declared, lambda step_id: verified(step_id).output,
        run_input=run.input,
        load_evidence=lambda step_id: verified(step_id).evidence,
    )
    if not isinstance(resolved, dict):
        raise ValueError("resolved task input must be an object")
    return resolved
