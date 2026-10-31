"""Public restart regressions for deterministic durable attempt binding."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
import yaml

import factory.workflow.runtime.execution.runner as runner_module
from factory.workflow.runtime.envelope import Envelope
from factory.workflow.runtime.run_binding import DurableAttemptBindingError
from factory.workflow.runtime.runtime import WorkflowRuntime


class InvocationCrash(BaseException):
    pass


class ProjectionCrash(BaseException):
    pass


class Invoker:
    def __init__(self, *, crash_once: bool = False) -> None:
        self.calls = []
        self.crash_once = crash_once

    def invoke(self, *, target, arguments, idempotency_key, envelope):
        self.calls.append((target, arguments, idempotency_key, envelope))
        if self.crash_once:
            self.crash_once = False
            raise InvocationCrash("after claim and invocation")
        return {"ok": True, "result": {
            "kind": "tool", "content": [], "meta": {},
            "structured_content": {"value": arguments.get("value", 1)},
        }}


def _config(tmp_path: Path, definition: dict) -> Path:
    config = tmp_path / "config"
    (config / "workflows").mkdir(parents=True)
    (config / "settings.yaml").write_text(yaml.safe_dump({
        "storage": {"backend": "sqlite", "sqlite": {"filename": "state.db"}},
        "durable_tasks": {"allowlist": {
            "work": {"brick_name": "demo", "tool_name": "work"},
            "consume": {"brick_name": "demo", "tool_name": "consume"},
        }},
    }))
    (config / "workflows" / "workflow.yaml").write_text(yaml.safe_dump(definition))
    return config


def _task(step_id: str = "work", *, task_type: str = "work",
          next_step: str | None = None, payload: dict | None = None) -> dict:
    return {
        "id": step_id, "kind": "task", "task_mode": "named_mcp",
        "task_type": task_type, "next": next_step,
        "task_payload": payload or {"value": 1},
        "idempotency_key_argument": "attempt_key",
    }


def _snapshot(database: Path) -> tuple:
    with sqlite3.connect(database) as conn:
        return tuple(
            tuple(conn.execute(f"SELECT * FROM {table} ORDER BY rowid").fetchall())
            for table in ("runs", "step_executions", "task_attempts", "events")
        )


def _observe_nothing(monkeypatch: pytest.MonkeyPatch) -> tuple[list, list]:
    events: list = []
    graph_syncs: list = []
    monkeypatch.setattr(
        runner_module, "emit_workflow_event", lambda *args: events.append(args),
    )
    monkeypatch.setattr(runner_module, "sync_run", lambda *args: graph_syncs.append(args))
    return events, graph_syncs


@pytest.mark.parametrize("expired", [False, True], ids=["busy", "expired"])
@pytest.mark.parametrize("corruption", ["input", "attempt_id"])
def test_tampered_running_attempt_blocks_public_restart_without_mutation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    expired: bool, corruption: str,
) -> None:
    definition = {
        "schema_version": "v2", "id": "wf", "name": "WF",
        "steps": [_task()],
    }
    invoker, config = Invoker(crash_once=True), _config(tmp_path, definition)
    with pytest.raises(InvocationCrash):
        WorkflowRuntime.from_config_dir(config, tool_invoker=invoker).start_run(
            workflow_name_or_id="wf", input={}, run_key="running",
            envelope=Envelope(),
        )
    database = config / "state.db"
    with sqlite3.connect(database) as conn:
        if corruption == "input":
            conn.execute(
                "UPDATE task_attempts SET input_json=?",
                ('{"attempt_key":"forged","value":1}',),
            )
        else:
            conn.execute("UPDATE task_attempts SET attempt_id='forged'")
        if expired:
            conn.execute(
                "UPDATE task_attempts SET lease_expires_at='2000-01-01T00:00:00+00:00'"
            )
        run_id = str(conn.execute("SELECT run_id FROM runs").fetchone()[0])
    before = _snapshot(database)
    events, graph_syncs = _observe_nothing(monkeypatch)
    restarted = WorkflowRuntime.from_config_dir(config, tool_invoker=invoker)
    with pytest.raises(DurableAttemptBindingError, match=corruption):
        restarted.resume_run(run_id=run_id, envelope=Envelope())
    assert len(invoker.calls) == 1
    assert _snapshot(database) == before
    assert events == [] and graph_syncs == []


def test_tampered_succeeded_attempt_blocks_recovery_without_reinvoke(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    definition = {
        "schema_version": "v2", "id": "wf", "name": "WF",
        "result_projection": {
            "value": {"$ref": "workflow-step:///work/output#/value"},
        }, "steps": [_task()],
    }
    invoker, config = Invoker(), _config(tmp_path, definition)
    runtime = WorkflowRuntime.from_config_dir(config, tool_invoker=invoker)
    original = runtime.storage.update_run

    def stop_projection(**kwargs):
        if kwargs["status"] == "succeeded":
            raise ProjectionCrash()
        return original(**kwargs)

    runtime.storage.update_run = stop_projection
    with pytest.raises(ProjectionCrash):
        runtime.start_run(
            workflow_name_or_id="wf", input={}, run_key="succeeded",
            envelope=Envelope(),
        )
    database = config / "state.db"
    with sqlite3.connect(database) as conn:
        conn.execute("UPDATE task_attempts SET input_json='{}'")
        run_id = str(conn.execute("SELECT run_id FROM runs").fetchone()[0])
    before = _snapshot(database)
    events, graph_syncs = _observe_nothing(monkeypatch)
    restarted = WorkflowRuntime.from_config_dir(config, tool_invoker=invoker)
    with pytest.raises(DurableAttemptBindingError, match="input"):
        restarted.resume_run(run_id=run_id, envelope=Envelope())
    assert len(invoker.calls) == 1
    assert _snapshot(database) == before
    assert events == [] and graph_syncs == []


def test_coherently_tampered_succeeded_input_is_rejected_during_projection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    definition = {
        "schema_version": "v2", "id": "wf", "name": "WF",
        "steps": [
            _task("produce", next_step="wait"),
            {"id": "wait", "kind": "wait_for_event", "event_type": "continue",
             "next": "consume"},
            _task("consume", task_type="consume", payload={
                "value": {"$ref": "workflow-step:///produce/output#/value"},
            }),
        ],
    }
    invoker, config = Invoker(), _config(tmp_path, definition)
    started = WorkflowRuntime.from_config_dir(config, tool_invoker=invoker).start_run(
        workflow_name_or_id="wf", input={}, run_key="projection", envelope=Envelope(),
    )
    database = config / "state.db"
    with sqlite3.connect(database) as conn:
        conn.execute(
            "UPDATE runs SET status='running',current_step_id='consume',"
            "waiting_for_event_type=NULL WHERE run_id=?", (started["run_id"],),
        )
        attempt_id = conn.execute("SELECT attempt_id FROM task_attempts").fetchone()[0]
        conn.execute("UPDATE step_executions SET input_json='{\"value\":999}'")
        conn.execute("UPDATE task_attempts SET input_json=?", (
            f'{{"attempt_key":"{attempt_id}","value":999}}',
        ))
    before = _snapshot(database)
    events, graph_syncs = _observe_nothing(monkeypatch)
    restarted = WorkflowRuntime.from_config_dir(config, tool_invoker=invoker)
    with pytest.raises(DurableAttemptBindingError, match="input"):
        restarted.step_run(run_id=started["run_id"], envelope=Envelope())
    assert len(invoker.calls) == 1
    assert _snapshot(database) == before
    assert events == [] and graph_syncs == []
