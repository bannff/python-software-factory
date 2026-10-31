"""Restart regressions for durable recovery, authority, and busy polling."""
from __future__ import annotations

import sqlite3
import threading
from dataclasses import dataclass, field
from pathlib import Path

import pytest
import yaml

from factory.workflow.runtime.envelope import Envelope
from factory.workflow.runtime.runtime import WorkflowRuntime


@dataclass
class InvokeState:
    calls: list = field(default_factory=list)
    wrappers: int = 0


class SuccessInvoker:
    def __init__(self, state: InvokeState):
        self.state = state
        state.wrappers += 1

    def invoke(self, *, target, arguments, idempotency_key, envelope):
        self.state.calls.append((target, arguments, idempotency_key, envelope))
        return {"ok": True, "result": {
            "kind": "tool", "content": [], "meta": {},
            "structured_content": {"value": arguments.get("value", 1)},
        }}


@dataclass
class BlockingState(InvokeState):
    started: threading.Event = field(default_factory=threading.Event)
    release: threading.Event = field(default_factory=threading.Event)
    commits: dict[str, int] = field(default_factory=dict)


class BlockingInvoker(SuccessInvoker):
    def invoke(self, *, target, arguments, idempotency_key, envelope):
        self.state.calls.append((target, arguments, idempotency_key, envelope))
        self.state.started.set()
        assert self.state.release.wait(timeout=10)
        self.state.commits[idempotency_key] = self.state.commits.get(idempotency_key, 0) + 1
        return {"ok": True, "result": {
            "kind": "tool", "content": [], "meta": {},
            "structured_content": {"value": 1},
        }}


def _config(tmp_path: Path) -> Path:
    config = tmp_path / "config"
    (config / "workflows").mkdir(parents=True)
    (config / "settings.yaml").write_text(yaml.safe_dump({
        "storage": {"backend": "sqlite", "sqlite": {"filename": "state.db"}},
        "durable_tasks": {"allowlist": {
            "work": {"brick_name": "demo", "tool_name": "work"},
        }},
    }))
    definitions = ({
        "id": "recover", "name": "Recover", "steps": [
            {"id": "work", "kind": "task", "task_mode": "named_mcp",
             "task_type": "work", "next": "wait"},
            {"id": "wait", "kind": "wait_for_event", "event_type": "continue"},
        ],
    }, {
        "id": "busy", "name": "Busy", "steps": [
            {"id": "work", "kind": "task", "task_mode": "named_mcp",
             "task_type": "work", "lease_seconds": 30},
        ],
    })
    for definition in definitions:
        (config / "workflows" / f"{definition['id']}.yaml").write_text(
            yaml.safe_dump(definition)
        )
    return config


def _runtime(config: Path, state: InvokeState, blocking: bool = False):
    invoker = BlockingInvoker(state) if blocking else SuccessInvoker(state)
    return WorkflowRuntime.from_config_dir(config, tool_invoker=invoker)


def _crash_to_succeeded_step(config: Path, run_id: str) -> None:
    with sqlite3.connect(config / "state.db") as conn:
        conn.execute(
            "UPDATE runs SET status='running',current_step_id='work',"
            "waiting_for_event_type=NULL WHERE run_id=?", (run_id,),
        )


def _start_recovery(config: Path, state: InvokeState, envelope: Envelope):
    return _runtime(config, state).start_run(
        workflow_name_or_id="recover", input={"value": 7},
        run_key="recover-key", envelope=envelope,
    )


def test_succeeded_recovery_reloads_durable_output_without_reinvoke(tmp_path: Path) -> None:
    config, state, envelope = _config(tmp_path), InvokeState(), Envelope()
    started = _start_recovery(config, state, envelope)
    _crash_to_succeeded_step(config, started["run_id"])
    resumed = _runtime(config, state).resume_run(
        run_id=started["run_id"], envelope=envelope,
    )
    assert resumed["status"] == "waiting"
    assert len(state.calls) == 1
    assert state.wrappers == 2


@pytest.mark.parametrize("table,column,value", [
    ("step_executions", "output_json", '{"value":2}'),
    ("task_attempts", "evidence_json", "{}"),
    ("task_attempts", "envelope_json", "{}"),
    ("task_attempts", "output_digest", "0" * 64),
])
def test_succeeded_recovery_rejects_tamper_without_reinvoke(
    tmp_path: Path, table: str, column: str, value: str,
) -> None:
    config, state, envelope = _config(tmp_path), InvokeState(), Envelope()
    started = _start_recovery(config, state, envelope)
    _crash_to_succeeded_step(config, started["run_id"])
    with sqlite3.connect(config / "state.db") as conn:
        conn.execute(f"UPDATE {table} SET {column}=?", (value,))
    result = _runtime(config, state).resume_run(
        run_id=started["run_id"], envelope=envelope,
    )
    assert result["status"] == "failed"
    assert len(state.calls) == 1


@pytest.mark.parametrize("action", ["start", "resume", "step", "emit", "cancel"])
def test_named_mutations_reject_authority_mismatch_without_invocation(
    tmp_path: Path, action: str,
) -> None:
    config, state = _config(tmp_path), InvokeState()
    initial = Envelope(tenant_id="t", principal_id="p", session_id="s", agent_id="a",
                       attributes={"role": "operator"}, correlation_id="initial")
    started = _start_recovery(config, state, initial)
    mismatched = initial.model_copy(update={"principal_id": "other"})
    runtime = _runtime(config, state)
    calls = {
        "start": lambda: runtime.start_run(workflow_name_or_id="recover", input={"value": 7},
                                            run_key="recover-key", envelope=mismatched),
        "resume": lambda: runtime.resume_run(run_id=started["run_id"], envelope=mismatched),
        "step": lambda: runtime.step_run(run_id=started["run_id"], envelope=mismatched),
        "emit": lambda: runtime.emit_event(run_id=started["run_id"], event_type="continue",
                                            payload={}, envelope=mismatched),
        "cancel": lambda: runtime.cancel_run(run_id=started["run_id"], reason="x",
                                              envelope=mismatched),
    }
    with pytest.raises(ValueError, match="authority mismatch"):
        calls[action]()
    assert len(state.calls) == 1


def test_busy_poll_keeps_run_revision_and_owner_can_complete(tmp_path: Path) -> None:
    config, state = _config(tmp_path), BlockingState()
    envelope, owner = Envelope(), {}

    def start_owner():
        owner.update(_runtime(config, state, blocking=True).start_run(
            workflow_name_or_id="busy", input={}, run_key="busy-key", envelope=envelope,
        ))

    thread = threading.Thread(target=start_owner)
    thread.start()
    assert state.started.wait(timeout=10)
    with sqlite3.connect(config / "state.db") as conn:
        run_id, before = conn.execute(
            "SELECT run_id,revision FROM runs WHERE run_key='busy-key'"
        ).fetchone()
    polled = _runtime(config, state, blocking=True).resume_run(
        run_id=run_id, envelope=envelope,
    )
    with sqlite3.connect(config / "state.db") as conn:
        after = conn.execute("SELECT revision FROM runs WHERE run_id=?", (run_id,)).fetchone()[0]
    assert polled["status"] == "running" and after == before
    state.release.set()
    thread.join(timeout=10)
    assert not thread.is_alive()
    assert owner["status"] == "succeeded"
    assert len(state.calls) == 1
    assert list(state.commits.values()) == [1]
