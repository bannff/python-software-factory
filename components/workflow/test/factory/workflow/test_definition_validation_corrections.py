"""Definition-time validation for executable projection and target contracts."""
from __future__ import annotations

import pytest

from factory.workflow.runtime.models import StepDefinition, WorkflowDefinition


def _named(step_id: str, *, next_step: str | None = None) -> dict:
    return {"id": step_id, "kind": "task", "task_mode": "named_mcp",
            "task_type": "work", "next": next_step}


@pytest.mark.parametrize("task_type", [None, "", "   "])
def test_direct_named_target_still_requires_task_type(task_type: str | None) -> None:
    with pytest.raises(ValueError, match="non-empty task_type"):
        StepDefinition.model_validate({
            "id": "work", "kind": "task", "task_mode": "named_mcp",
            "task_type": task_type,
            "tool_target": {"brick_name": "demo", "tool_name": "work"},
        })


@pytest.mark.parametrize("steps", [
    [{"id": "end", "kind": "task", "task_type": "local"}],
    [_named("first", next_step="end"),
     {"id": "end", "kind": "task", "task_type": "local"}],
    [{"id": "end", "kind": "wait_for_event", "event_type": "continue"}],
    [{"id": "end", "kind": "noop"}],
    [_named("one", next_step="two"), _named("two", next_step="one")],
])
def test_projection_rejects_non_named_or_missing_terminal_paths(steps: list[dict]) -> None:
    with pytest.raises(ValueError, match="named_mcp terminal"):
        WorkflowDefinition.model_validate({
            "schema_version": "v2", "id": "wf", "name": "WF",
            "result_projection": {"value": 1}, "steps": steps,
        })


def test_projection_accepts_mixed_workflow_with_named_terminal() -> None:
    workflow = WorkflowDefinition.model_validate({
        "schema_version": "v2", "id": "wf", "name": "WF",
        "result_projection": {"value": 1},
        "steps": [
            {"id": "prepare", "kind": "task", "task_type": "local", "next": "finish"},
            _named("finish"),
        ],
    })
    assert workflow.get_step("finish").task_mode == "named_mcp"


def test_frozen_bound_named_target_remains_valid() -> None:
    step = StepDefinition.model_validate({
        **_named("work"),
        "tool_target": {"brick_name": "demo", "tool_name": "work"},
    })
    assert step.task_type == "work" and step.tool_target is not None
