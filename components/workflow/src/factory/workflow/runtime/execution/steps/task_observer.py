"""Narrow observation helper for lease-fenced task owners."""
from __future__ import annotations

from typing import Any

from factory.workflow.runtime.ports import DurableWorkflowStorage


def attempt_after_stale_fence(
    durable: DurableWorkflowStorage, *, run_id: str, attempt_id: str,
    error: ValueError, expected: str,
) -> dict[str, Any]:
    """Return the latest step attempt only for an exact stale-fence error."""
    if str(error) != expected:
        raise error
    attempts = durable.list_task_attempts(run_id=run_id)
    observed = next(
        (item for item in attempts if item.get("attempt_id") == attempt_id), None,
    )
    if observed is None:
        raise RuntimeError("fenced task attempt disappeared from durable journal") from error
    same_step = [
        item for item in attempts
        if item.get("step_execution_id") == observed.get("step_execution_id")
    ]
    return max(same_step, key=lambda item: int(item.get("attempt_number", 0)))
