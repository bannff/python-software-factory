"""Runtime-owned argument binding for durable named-MCP tasks."""
from __future__ import annotations

from factory.workflow.runtime.canonical import canonical_loads
from factory.workflow.runtime.models import RunRecord, StepDefinition
from factory.workflow.runtime.task_models import AttemptClaim


def execution_arguments(
    step: StepDefinition, run: RunRecord, claim: AttemptClaim,
) -> dict:
    """Add journal-owned identity without mutating frozen task input."""
    arguments = canonical_loads(claim.canonical_input)
    arguments.pop("engine_spec", None)
    injected = {
        step.run_id_argument: run.run_id,
        step.attempt_revision_argument: claim.revision,
    }
    for name, value in injected.items():
        if name is None:
            continue
        if name in arguments:
            raise ValueError(f"runtime argument collides with task payload: {name}")
        arguments[name] = value
    return arguments


__all__ = ["execution_arguments"]
