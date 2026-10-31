"""Execution-engine continuation policy and cap contracts."""
from __future__ import annotations

import pytest

from factory.workflow.runtime.execution_engines import ExecutionEngineSpec
from factory.workflow.runtime.execution_enrollment import definition
from factory.workflow.runtime.models import ToolTarget
from factory.workflow.runtime.task_models import PayloadPredicate, TaskOutcomePolicy


def _policy(continued: bool = True) -> TaskOutcomePolicy:
    return TaskOutcomePolicy(
        success=PayloadPredicate(pointer="/status", equals="completed"),
        continuation=PayloadPredicate(pointer="/status", equals="partial")
        if continued else None,
        retryable=PayloadPredicate(pointer="/retryable", equals=True),
    )


def _spec(**changes) -> ExecutionEngineSpec:
    values = {
        "engine_id": "progress", "invoke_target": ToolTarget(
            brick_name="migration", tool_name="migration_apply_execution"),
        "outcome": _policy(), "max_attempts": 3, "max_continuations": 7,
    }
    values.update(changes)
    return ExecutionEngineSpec(**values)


def test_engine_freezes_separate_retry_and_continuation_caps() -> None:
    step = definition(_spec(), {}).steps[0]
    assert step.max_attempts == 3
    assert step.max_continuations == 7
    assert step.task_outcome.continuation.pointer == "/status"


def test_continuation_and_cap_must_be_declared_together() -> None:
    with pytest.raises(ValueError, match="positive cap"):
        _spec(max_continuations=0)
    with pytest.raises(ValueError, match="positive cap"):
        _spec(outcome=_policy(False), max_continuations=7)
