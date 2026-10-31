"""Focused regression tests for reopened durable-workflow review blockers."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest
import yaml

from factory.workflow.runtime.envelope import Envelope
from factory.workflow.runtime.execution.adapters import TaskResult, TaskStatus
from factory.workflow.runtime.models import Settings, StepDefinition, WorkflowDefinition
from factory.workflow.runtime.operations import WorkflowError
from factory.workflow.runtime.runtime import WorkflowRuntime
from factory.workflow.runtime.storage.sqlite import SqliteWorkflowStorage

TARGETS = {
    "work": {"brick_name": "demo", "tool_name": "work"},
    "consume": {"brick_name": "demo", "tool_name": "consume"},
}


class SuccessInvoker:
    def __init__(self):
        self.calls = []

    def invoke(self, *, target, arguments, idempotency_key, envelope):
        self.calls.append((target, arguments, idempotency_key, envelope))
        return {"ok": True, "result": {"kind": "tool", "content": [], "meta": {},
                                       "structured_content": {"value": arguments.get("value", 1)}}}


def _config(tmp_path: Path, *, waiting: bool = False) -> Path:
    config = tmp_path / "config"
    (config / "workflows").mkdir(parents=True)
    (config / "settings.yaml").write_text(yaml.safe_dump({
        "storage": {"backend": "sqlite", "sqlite": {"filename": "state.db"}},
        "durable_tasks": {"allowlist": TARGETS},
    }))
    steps = [{"id": "work", "kind": "task", "task_mode": "named_mcp",
              "task_type": "work"}]
    if waiting:
        steps[0]["next"] = "wait"
        steps.extend([
            {"id": "wait", "kind": "wait_for_event", "event_type": "continue",
             "next": "consume"},
            {"id": "consume", "kind": "task", "task_mode": "named_mcp",
             "task_type": "consume", "task_payload": {
                 "value": {"$ref": "workflow-step:///work/output#/value"},
             }},
        ])
    (config / "workflows" / "workflow.yaml").write_text(yaml.safe_dump({
        "id": "wf", "name": "Workflow", "version": 1, "steps": steps,
    }))
    return config


def test_run_key_reuse_conflicts_on_input_or_tenant(tmp_path: Path) -> None:
    config, invoker = _config(tmp_path), SuccessInvoker()
    runtime = WorkflowRuntime.from_config_dir(config, tool_invoker=invoker)
    first = runtime.start_run(
        workflow_name_or_id="wf", input={"value": 1}, run_key="stable",
        envelope=Envelope(tenant_id="tenant"),
    )
    assert first["run_id"].startswith("wfr:v1:")
    assert runtime.get_run(run_id=first["run_id"], envelope=Envelope())["run_key"] == "stable"
    with pytest.raises(WorkflowError, match="run-key conflict"):
        runtime.start_run(
            workflow_name_or_id="wf", input={"value": 2}, run_key="stable",
            envelope=Envelope(tenant_id="tenant"),
        )
    with pytest.raises(ValueError, match="authority mismatch"):
        runtime.start_run(
            workflow_name_or_id="wf", input={"value": 1}, run_key="stable",
            envelope=Envelope(tenant_id="other"),
        )


@pytest.mark.parametrize("column,value", [
    ("output_json", '{"value":2}'),
    ("output_digest", "0" * 64),
    ("evidence_json", "{}"),
    ("artifact_refs_json", '{"tampered":true}'),
])
def test_downstream_rejects_output_or_evidence_tamper(
    tmp_path: Path, column: str, value: str,
) -> None:
    config, invoker = _config(tmp_path, waiting=True), SuccessInvoker()
    runtime = WorkflowRuntime.from_config_dir(config, tool_invoker=invoker)
    started = runtime.start_run(
        workflow_name_or_id="wf", input={"value": 1}, run_key="tamper",
        envelope=Envelope(),
    )
    with sqlite3.connect(config / "state.db") as conn:
        conn.execute(f"UPDATE step_executions SET {column}=? WHERE step_id='work'", (value,))
    restarted = WorkflowRuntime.from_config_dir(config, tool_invoker=invoker)
    restarted.emit_event(
        run_id=started["run_id"], event_type="continue", payload={}, envelope=Envelope(),
    )
    result = restarted.step_run(run_id=started["run_id"], envelope=Envelope())
    assert result["status"] == "failed"
    with sqlite3.connect(config / "state.db") as conn:
        failed_step = conn.execute(
            "SELECT status,error FROM step_executions WHERE step_id='consume'",
        ).fetchone()
    assert failed_step is not None and failed_step[0] == "failed"
    assert len(invoker.calls) == 1


class CancellingInvoker(SuccessInvoker):
    runtime = None

    def invoke(self, **kwargs):
        run = self.runtime.durable_storage.get_run_by_key(run_key="cancel-key")
        self.runtime.cancel_run(run_id=run.run_id, reason="concurrent", envelope=Envelope())
        return super().invoke(**kwargs)


def test_terminal_completion_cannot_overwrite_cancellation(tmp_path: Path) -> None:
    config, invoker = _config(tmp_path), CancellingInvoker()
    runtime = WorkflowRuntime.from_config_dir(config, tool_invoker=invoker)
    invoker.runtime = runtime
    result = runtime.start_run(
        workflow_name_or_id="wf", input={}, run_key="cancel-key", envelope=Envelope(),
    )
    assert result["status"] == "cancelled"
    assert runtime.get_run(run_id=result["run_id"], envelope=Envelope())["status"] == "cancelled"


class RecordingExecutor:
    backend_name = "recording"

    def __init__(self):
        self.submissions = []

    def health_check(self):
        return {"ok": True, "backend": self.backend_name}

    def submit(self, **kwargs):
        self.submissions.append(kwargs)
        return TaskResult(task_id=kwargs["task_id"], status=TaskStatus.SUCCEEDED,
                          result={"legacy": True})

    def get_status(self, **kwargs):
        raise AssertionError("not expected")

    def cancel(self, **kwargs):
        raise AssertionError("not expected")

    def list_tasks(self, **kwargs):
        return []


def test_default_task_mode_preserves_legacy_executor_and_options(tmp_path: Path) -> None:
    storage, executor = SqliteWorkflowStorage(tmp_path / "legacy.db"), RecordingExecutor()
    named = SuccessInvoker()
    storage.init_schema()
    workflow = WorkflowDefinition(id="legacy", name="Legacy", steps=[StepDefinition(
        id="task", kind="task", task_type="local", task_options={"queue": "critical"},
    )])
    runtime = WorkflowRuntime(
        config_dir=tmp_path, settings=Settings(), settings_raw={}, workflows=[workflow],
        storage=storage, executor=executor, tool_invoker=named,
    )
    result = runtime.start_run(
        workflow_name_or_id="legacy", input={"x": 1}, envelope=Envelope(run_id="legacy-run"),
    )
    assert result["status"] == "succeeded"
    assert executor.submissions[0]["options"] == {"queue": "critical"}
    assert executor.submissions[0]["payload"] == {"x": 1}
    assert named.calls == []


def test_loaded_run_transition_rejects_stale_revision(tmp_path: Path) -> None:
    storage = SqliteWorkflowStorage(tmp_path / "cas.db")
    storage.init_schema()
    now = datetime.now(timezone.utc)
    run = storage.create_run(
        run_id="run", workflow_id="wf", workflow_version=1, tenant_id=None,
        input={}, envelope=Envelope(), now=now,
    )
    storage.update_run(
        run_id="run", status="running", current_step_id="one",
        waiting_for_event_type=None, last_event_id=None, result=None, error=None,
        now=now, expected_statuses={"running"}, expected_revision=run.revision,
    )
    with pytest.raises(ValueError, match="stale run transition"):
        storage.update_run(
            run_id="run", status="failed", current_step_id="stale",
            waiting_for_event_type=None, last_event_id=None, result=None, error="late",
            now=now, expected_statuses={"running"}, expected_revision=run.revision,
        )
    assert storage.get_run(run_id="run").current_step_id == "one"
