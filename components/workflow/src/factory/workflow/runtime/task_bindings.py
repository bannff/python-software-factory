"""Bind named task aliases to immutable gateway targets."""
from __future__ import annotations

from .models import ToolTarget, WorkflowDefinition


def bind_named_targets(
    workflow: WorkflowDefinition, allowlist: dict[str, ToolTarget],
) -> WorkflowDefinition:
    """Return the exact executable definition persisted for a new run."""
    steps = []
    for step in workflow.steps:
        if step.kind != "task" or step.task_mode != "named_mcp":
            steps.append(step)
            continue
        target = allowlist.get(step.task_type or "")
        if target is None:
            raise ValueError(f"unknown or disallowed task type: {step.task_type}")
        if step.tool_target is not None and step.tool_target != target:
            raise ValueError(f"named MCP binding conflict for step: {step.id}")
        steps.append(step.model_copy(update={"tool_target": target}))
    return workflow.model_copy(update={"steps": steps})
