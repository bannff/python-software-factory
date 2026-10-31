"""Restart integration for frozen bindings, refs, and durable output."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import pytest
import yaml

from factory.workflow.runtime.envelope import Envelope
from factory.workflow.runtime.operations import WorkflowError
from factory.workflow.runtime.runtime import WorkflowRuntime


@dataclass
class RecordingState:
    calls: list = field(default_factory=list)
    wrappers: int = 0


class RecordingInvoker:
    def __init__(self, state: RecordingState):
        self.state = state
        state.wrappers += 1

    def invoke(self, *, target, arguments, idempotency_key, envelope):
        self.state.calls.append((target, arguments, idempotency_key, envelope))
        if target.tool_name == "prepare":
            digest = "a" * 64
            output = {"artifacts": {"model": {
                "uri": "file:///model.bin", "sha256": digest,
                "evidence": {"sha256": digest},
            }}}
        else:
            assert target.tool_name == "train"
            assert arguments["model_uri"] == "file:///model.bin"
            output = {"error": "domain-output-is-not-transport"}
        return {"ok": True, "result": {
            "kind": "tool", "content": [], "meta": {},
            "structured_content": output,
        }}


def _config(tmp_path: Path) -> Path:
    config = tmp_path / "config"
    (config / "workflows").mkdir(parents=True)
    (config / "settings.yaml").write_text(yaml.safe_dump({
        "storage": {"backend": "sqlite", "sqlite": {"filename": "state.db"}},
        "durable_tasks": {"allowlist": {
            "prepare": {"brick_name": "dataset", "tool_name": "prepare"},
            "train": {"brick_name": "machine_learning", "tool_name": "train"},
        }},
    }))
    definition = {
        "id": "pipeline", "name": "Pipeline", "version": 1,
        "steps": [
            {"id": "prepare", "kind": "task", "task_mode": "named_mcp",
             "task_type": "prepare", "next": "gate"},
            {"id": "gate", "kind": "wait_for_event", "event_type": "continue",
             "next": "train"},
            {"id": "train", "kind": "task", "task_mode": "named_mcp",
             "task_type": "train", "task_payload": {
                 "model_uri": {"$ref": "workflow-step:///prepare/output#/artifacts/model/uri"},
             }},
        ],
    }
    (config / "workflows" / "pipeline.yaml").write_text(yaml.safe_dump(definition))
    return config


def _runtime(config: Path, state: RecordingState, allowlist=None) -> WorkflowRuntime:
    return WorkflowRuntime.from_config_dir(
        config, tool_invoker=RecordingInvoker(state), task_allowlist=allowlist,
    )


def test_restart_uses_frozen_snapshot_and_no_duplicate_completion(tmp_path: Path) -> None:
    config, state = _config(tmp_path), RecordingState()
    initiation = Envelope(
        tenant_id="tenant", principal_id="principal", session_id="session",
        request_id="initial-request", correlation_id="initial-correlation",
        workflow_id="caller-workflow", run_id="caller-run", agent_id="agent",
        tool_name="caller-tool", timestamp=datetime(2026, 1, 2, tzinfo=timezone.utc),
        attributes={"role": "operator", "attempt": 1},
    )
    started = _runtime(config, state).start_run(
        workflow_name_or_id="pipeline", input={"source": "fixture"},
        run_key="stable-run", envelope=initiation,
    )
    assert started["run_id"].startswith("wfr:v1:")
    assert started["status"] == "waiting"
    stored = _runtime(config, state).get_run(
        run_id=started["run_id"], envelope=initiation,
    )
    assert stored["initiation_envelope"] == initiation.model_dump()
    with sqlite3.connect(config / "state.db") as conn:
        persisted_envelope = conn.execute(
            "SELECT envelope_json FROM runs WHERE run_id=?", (started["run_id"],),
        ).fetchone()[0]
    assert persisted_envelope == initiation.model_dump_json()
    assert len(state.calls) == 1
    changed = yaml.safe_load((config / "workflows" / "pipeline.yaml").read_text())
    changed["steps"][2]["task_type"] = "disallowed-after-start"
    changed["steps"][2]["task_payload"] = {"model_uri": "wrong"}
    (config / "workflows" / "pipeline.yaml").write_text(yaml.safe_dump(changed))

    resumed = _runtime(config, state, {}).start_run(
        workflow_name_or_id="pipeline", input={"source": "fixture"},
        run_key="stable-run", envelope=initiation,
    )
    assert resumed["run_id"] == started["run_id"]
    assert resumed["status"] == "waiting"
    assert len(state.calls) == 1
    action_envelope = Envelope(
        tenant_id="tenant", principal_id="principal", session_id="session",
        request_id="resume-request", correlation_id="resume-correlation",
        workflow_id="resume-workflow", run_id="resume-run", agent_id="agent",
        tool_name="resume-tool", timestamp=datetime(2026, 2, 3, tzinfo=timezone.utc),
        attributes={"role": "operator", "attempt": 1},
    )
    _runtime(config, state).emit_event(
        run_id=started["run_id"], event_type="continue", payload={},
        envelope=action_envelope,
    )
    with sqlite3.connect(config / "state.db") as conn:
        event_envelope = conn.execute(
            "SELECT envelope_json FROM events WHERE event_type='continue'",
        ).fetchone()[0]
    assert event_envelope == action_envelope.model_dump_json()
    assert _runtime(config, state).step_run(
        run_id=started["run_id"], envelope=action_envelope,
    )["status"] == "succeeded"
    assert [call[0].tool_name for call in state.calls] == ["prepare", "train"]
    expected = initiation.model_copy(update={
        "workflow_id": "pipeline", "run_id": started["run_id"],
    })
    assert all(
        call[3].model_dump_json() == expected.model_dump_json()
        for call in state.calls
    )
    assert _runtime(config, state).step_run(
        run_id=started["run_id"], envelope=action_envelope,
    )["status"] == "succeeded"
    assert len(state.calls) == 2
    assert state.wrappers >= 5


def test_new_run_binding_drift_at_same_version_conflicts(tmp_path: Path) -> None:
    config, state = _config(tmp_path), RecordingState()
    _runtime(config, state).start_run(
        workflow_name_or_id="pipeline", input={}, run_key="first", envelope=Envelope(),
    )
    drift = {
        "prepare": {"brick_name": "other", "tool_name": "changed"},
        "train": {"brick_name": "machine_learning", "tool_name": "train"},
    }
    with pytest.raises(WorkflowError, match="workflow-version conflict"):
        _runtime(config, state, drift).start_run(
            workflow_name_or_id="pipeline", input={}, run_key="second", envelope=Envelope(),
        )
