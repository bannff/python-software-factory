"""Public-runtime restart regressions for durable run identity binding."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
import yaml

from factory.workflow.runtime.envelope import Envelope
from factory.workflow.runtime.run_binding import DurableRunBindingError
from factory.workflow.runtime.runtime import WorkflowRuntime


class Invoker:
    def __init__(self) -> None:
        self.calls = []

    def invoke(self, *, target, arguments, idempotency_key, envelope):
        self.calls.append((target, arguments, idempotency_key, envelope))
        return {"ok": True, "result": {
            "kind": "tool", "content": [], "meta": {},
            "structured_content": {"value": arguments.get("value", 1)},
        }}


class ProjectionCrash(BaseException):
    pass


def _config(tmp_path: Path, definition: dict) -> Path:
    config = tmp_path / "config"
    (config / "workflows").mkdir(parents=True)
    (config / "settings.yaml").write_text(yaml.safe_dump({
        "storage": {"backend": "sqlite", "sqlite": {"filename": "state.db"}},
        "durable_tasks": {"allowlist": {
            "work": {"brick_name": "demo", "tool_name": "work"},
        }},
    }))
    (config / "workflows" / "workflow.yaml").write_text(yaml.safe_dump(definition))
    return config


def _snapshot(database: Path) -> tuple:
    with sqlite3.connect(database) as conn:
        run = conn.execute(
            "SELECT status,revision,result_json,error FROM runs"
        ).fetchone()
        counts = tuple(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                       for table in ("step_executions", "task_attempts", "events"))
    return (*run, *counts)


def _tamper_input(database: Path) -> None:
    with sqlite3.connect(database) as conn:
        conn.execute("UPDATE runs SET input_json=?", ('{"value":999}',))


def _run_id(database: Path) -> str:
    with sqlite3.connect(database) as conn:
        return str(conn.execute("SELECT run_id FROM runs").fetchone()[0])


def test_tampered_run_input_cannot_invoke_projected_named_tool(tmp_path: Path) -> None:
    definition = {
        "schema_version": "v2", "id": "wf", "name": "WF",
        "steps": [
            {"id": "wait", "kind": "wait_for_event", "event_type": "continue",
             "next": "work"},
            {"id": "work", "kind": "task", "task_mode": "named_mcp",
             "task_type": "work", "task_payload": {
                 "value": {"$ref": "workflow-run:///input#/value"},
             }},
        ],
    }
    invoker, config = Invoker(), _config(tmp_path, definition)
    runtime = WorkflowRuntime.from_config_dir(config, tool_invoker=invoker)
    started = runtime.start_run(
        workflow_name_or_id="wf", input={"value": 1}, run_key="projected",
        envelope=Envelope(),
    )
    runtime.emit_event(
        run_id=started["run_id"], event_type="continue", payload={}, envelope=Envelope(),
    )
    database = config / "state.db"
    _tamper_input(database)
    before = _snapshot(database)
    restarted = WorkflowRuntime.from_config_dir(config, tool_invoker=invoker)
    with pytest.raises(DurableRunBindingError, match="run_id"):
        restarted.step_run(run_id=started["run_id"], envelope=Envelope())
    assert invoker.calls == []
    assert _snapshot(database) == before


def test_tampered_run_input_cannot_publish_terminal_projection(tmp_path: Path) -> None:
    definition = {
        "schema_version": "v2", "id": "wf", "name": "WF",
        "result_projection": {
            "submitted": {"$ref": "workflow-run:///input#/value"},
            "produced": {"$ref": "workflow-step:///work/output#/value"},
        },
        "steps": [{"id": "work", "kind": "task", "task_mode": "named_mcp",
                   "task_type": "work", "task_payload": {"value": 1}}],
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
            workflow_name_or_id="wf", input={"value": 1}, run_key="terminal",
            envelope=Envelope(),
        )
    database = config / "state.db"
    _tamper_input(database)
    before = _snapshot(database)
    restarted = WorkflowRuntime.from_config_dir(config, tool_invoker=invoker)
    with pytest.raises(DurableRunBindingError, match="run_id"):
        restarted.resume_run(run_id=_run_id(database), envelope=Envelope())
    assert len(invoker.calls) == 1
    assert before[2] is None and _snapshot(database) == before


@pytest.mark.parametrize("action", ["start", "resume", "step", "emit", "cancel"])
def test_bad_run_execution_binding_blocks_public_mutations(
    tmp_path: Path, action: str,
) -> None:
    definition = {
        "schema_version": "v2", "id": "wf", "name": "WF",
        "steps": [
            {"id": "wait", "kind": "wait_for_event", "event_type": "continue",
             "next": "work"},
            {"id": "work", "kind": "task", "task_mode": "named_mcp",
             "task_type": "work"},
        ],
    }
    invoker, config = Invoker(), _config(tmp_path, definition)
    runtime = WorkflowRuntime.from_config_dir(config, tool_invoker=invoker)
    started = runtime.start_run(
        workflow_name_or_id="wf", input={"value": 1}, run_key="bound",
        envelope=Envelope(),
    )
    database = config / "state.db"
    with sqlite3.connect(database) as conn:
        conn.execute("UPDATE runs SET run_execution_id='forged'")
    before = _snapshot(database)
    restarted = WorkflowRuntime.from_config_dir(config, tool_invoker=invoker)
    operations = {
        "start": lambda: restarted.start_run(
            workflow_name_or_id="wf", input={"value": 1}, run_key="bound",
            envelope=Envelope(),
        ),
        "resume": lambda: restarted.resume_run(
            run_id=started["run_id"], envelope=Envelope(),
        ),
        "step": lambda: restarted.step_run(
            run_id=started["run_id"], envelope=Envelope(),
        ),
        "emit": lambda: restarted.emit_event(
            run_id=started["run_id"], event_type="continue", payload={}, envelope=Envelope(),
        ),
        "cancel": lambda: restarted.cancel_run(
            run_id=started["run_id"], reason="stop", envelope=Envelope(),
        ),
    }
    with pytest.raises(DurableRunBindingError, match="run_execution_id"):
        operations[action]()
    assert invoker.calls == []
    assert _snapshot(database) == before
