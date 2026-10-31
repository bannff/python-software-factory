"""Workflow continuation outcomes preserve a separate failure retry budget."""
from __future__ import annotations

from factory.workflow.runtime.envelope import Envelope
from factory.workflow.runtime.runtime import WorkflowRuntime
from factory.workflow.runtime.task_models import PayloadPredicate, TaskOutcomePolicy
from factory.workflow.runtime.task_outcomes import classify_outcome

from .test_projected_named_mcp import SequenceInvoker, _config, _step

_POLICY = {
    "success": {"pointer": "/status", "equals": "completed"},
    "continuation": {"pointer": "/status", "equals": "partial"},
    "retryable": {"pointer": "/retryable", "equals": True},
    "error_pointer": "/error",
}


def test_classifier_distinguishes_progress_from_retryable_failure() -> None:
    policy = TaskOutcomePolicy(
        success=PayloadPredicate(pointer="/status", equals="completed"),
        continuation=PayloadPredicate(pointer="/status", equals="partial"),
        retryable=PayloadPredicate(pointer="/retryable", equals=True),
    )
    progress = classify_outcome(
        {"status": "partial", "retryable": True}, policy)
    failure = classify_outcome(
        {"status": "failed", "retryable": True}, policy)
    assert progress.continued is True and progress.retryable is False
    assert failure.continued is False and failure.retryable is True


def _definition(max_continuations: int) -> dict:
    return {
        "schema_version": "v2", "id": "progress", "name": "Progress",
        "steps": [_step(
            max_attempts=2, max_continuations=max_continuations,
            idempotency_key_argument="attempt_id", task_outcome=_POLICY,
        )],
    }


def test_continuations_do_not_consume_failure_retry_budget(tmp_path) -> None:
    invoker = SequenceInvoker([
        {"status": "partial", "retryable": True, "error": ""},
        {"status": "failed", "retryable": True, "error": "transient"},
        {"status": "partial", "retryable": True, "error": ""},
        {"status": "completed", "retryable": False, "error": ""},
    ])
    runtime = WorkflowRuntime.from_config_dir(
        _config(tmp_path, _definition(3)), tool_invoker=invoker)
    run = runtime.start_run(
        workflow_name_or_id="progress", input={}, run_key="progress",
        envelope=Envelope())
    assert run["status"] == "succeeded"
    attempts = runtime.durable_storage.list_task_attempts(run_id=run["run_id"])
    assert [item["status"] for item in attempts] == [
        "continued", "failed", "continued", "succeeded",
    ]
    assert [item["attempt_number"] for item in attempts] == [1, 2, 3, 4]


def test_continuation_cap_fails_closed_without_using_retry_budget(tmp_path) -> None:
    invoker = SequenceInvoker([
        {"status": "partial", "retryable": True, "error": ""},
    ])
    runtime = WorkflowRuntime.from_config_dir(
        _config(tmp_path, _definition(2)), tool_invoker=invoker)
    run = runtime.start_run(
        workflow_name_or_id="progress", input={}, run_key="cap",
        envelope=Envelope())
    assert run["status"] == "failed"
    durable = runtime.get_run(run_id=run["run_id"], envelope=Envelope())
    assert durable["result"] == {"terminal_reason": "continuation_exhausted"}
    attempts = runtime.durable_storage.list_task_attempts(run_id=run["run_id"])
    assert [item["status"] for item in attempts] == ["continued", "continued"]
    assert len(invoker.calls) == 2
