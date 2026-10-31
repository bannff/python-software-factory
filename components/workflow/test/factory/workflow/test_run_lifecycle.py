from __future__ import annotations

from pathlib import Path

import yaml

from factory.workflow.runtime.envelope import parse_envelope
from factory.workflow.runtime.runtime import WorkflowRuntime


def _write_config(tmp_path: Path) -> Path:
    cfg = tmp_path / "config"
    cfg.mkdir()
    (cfg / "workflows").mkdir()
    (cfg / "settings.yaml").write_text(
        yaml.safe_dump(
            {
                "service": {"name": "workflow-module"},
                "storage": {"backend": "sqlite", "sqlite": {"filename": "state.sqlite"}},
                "authoring": {"enabled": False},
            },
            sort_keys=False,
        )
    )
    (cfg / "workflows" / "example.yaml").write_text(
        yaml.safe_dump(
            {
                "schema_version": "v1",
                "id": "example",
                "name": "Example Workflow",
                "version": 1,
                "steps": [
                    {"id": "start", "kind": "noop", "next": "wait"},
                    {"id": "wait", "kind": "wait_for_event", "event_type": "user.approved", "next": "done"},
                    {"id": "done", "kind": "noop"},
                ],
                "tags": ["test"],
            },
            sort_keys=False,
        )
    )
    return cfg


def test_start_run_idempotent_when_run_id_supplied(tmp_path: Path) -> None:
    cfg = _write_config(tmp_path)
    runtime = WorkflowRuntime.from_config_dir(cfg)
    env = parse_envelope({"run_id": "fixed", "tenant_id": "t1"})

    out1 = runtime.start_run(workflow_name_or_id="example", input={"x": 1}, envelope=env)
    out2 = runtime.start_run(workflow_name_or_id="example", input={"x": 2}, envelope=env)

    assert out1["run_id"] == "fixed"
    assert out2["run_id"] == "fixed"
    assert out1["status"] == "waiting"

    runtime.emit_event(run_id="fixed", event_type="user.approved", payload={"approved": True}, envelope=env)
    step = runtime.step_run(run_id="fixed", envelope=parse_envelope({"tenant_id": "t1"}))
    assert step["status"] == "succeeded"

    run = runtime.get_run(run_id="fixed", envelope=parse_envelope({"tenant_id": "t1"}))
    assert run["status"] == "succeeded"
