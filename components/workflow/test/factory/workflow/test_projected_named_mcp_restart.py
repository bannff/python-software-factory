"""Restart authority for frozen v1 semantics and verified v2 projections."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
import yaml

from factory.workflow.runtime.envelope import Envelope
from factory.workflow.runtime.runtime import WorkflowRuntime


class Invoker:
    def __init__(self):
        self.calls = []

    def invoke(self, *, target, arguments, idempotency_key, envelope):
        self.calls.append((target, arguments, idempotency_key, envelope))
        return {"ok": True, "result": {
            "kind": "tool", "content": [], "meta": {},
            "structured_content": {"value": 1},
        }}


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


def _task(payload: dict | None = None) -> dict:
    return {"id": "work", "kind": "task", "task_mode": "named_mcp",
            "task_type": "work", "task_payload": payload or {}}


class ProjectionCrash(BaseException):
    pass


def test_restart_projection_rejects_tampered_evidence_without_reinvoke(
    tmp_path: Path,
) -> None:
    definition = {
        "schema_version": "v2", "id": "wf", "name": "WF",
        "result_projection": {
            "evidence": {"$ref": "workflow-step:///work/evidence#"},
        }, "steps": [_task()],
    }
    invoker, config = Invoker(), _config(tmp_path, definition)
    crashed = WorkflowRuntime.from_config_dir(config, tool_invoker=invoker)
    original = crashed.storage.update_run

    def stop_projection(**kwargs):
        if kwargs["status"] == "succeeded":
            raise ProjectionCrash()
        return original(**kwargs)

    crashed.storage.update_run = stop_projection
    with pytest.raises(ProjectionCrash):
        crashed.start_run(
            workflow_name_or_id="wf", input={}, run_key="crash", envelope=Envelope(),
        )
    with sqlite3.connect(config / "state.db") as conn:
        conn.execute("UPDATE step_executions SET evidence_json='{}'")
        run_id = conn.execute("SELECT run_id FROM runs").fetchone()[0]
    restarted = WorkflowRuntime.from_config_dir(config, tool_invoker=invoker)
    result = restarted.resume_run(run_id=run_id, envelope=Envelope())
    assert result["status"] == "failed" and len(invoker.calls) == 1


def test_frozen_v1_snapshot_keeps_input_merge_after_v2_config_drift(
    tmp_path: Path,
) -> None:
    v1 = {
        "schema_version": "v1", "id": "wf", "name": "WF", "version": 1,
        "steps": [
            {"id": "wait", "kind": "wait_for_event", "event_type": "continue",
             "next": "work"},
            _task({"fixed": 2}),
        ],
    }
    invoker, config = Invoker(), _config(tmp_path, v1)
    runtime = WorkflowRuntime.from_config_dir(config, tool_invoker=invoker)
    started = runtime.start_run(
        workflow_name_or_id="wf", input={"legacy": 1},
        run_key="legacy", envelope=Envelope(),
    )
    assert started["status"] == "waiting" and invoker.calls == []
    v2 = {**v1, "schema_version": "v2", "steps": [v1["steps"][0], _task({"fixed": 3})]}
    (config / "workflows" / "workflow.yaml").write_text(yaml.safe_dump(v2))
    restarted = WorkflowRuntime.from_config_dir(config, tool_invoker=invoker)
    restarted.emit_event(
        run_id=started["run_id"], event_type="continue", payload={}, envelope=Envelope(),
    )
    result = restarted.step_run(run_id=started["run_id"], envelope=Envelope())
    assert result["status"] == "succeeded"
    assert invoker.calls[0][1] == {"legacy": 1, "fixed": 2}
