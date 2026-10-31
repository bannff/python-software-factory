"""Two-runtime regressions for reclaimed task-attempt lease fencing."""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest

import factory.workflow.runtime.execution.runner as runner_module
from factory.workflow.runtime.envelope import Envelope
from factory.workflow.runtime.execution.steps.task_observer import (
    attempt_after_stale_fence,
)
from factory.workflow.runtime.runtime import WorkflowRuntime
from .terminal_race_support import config_dir, run_id


@dataclass
class BlockingState:
    fail: bool = False
    calls: list[tuple[Any, ...]] = field(default_factory=list)
    started: threading.Event = field(default_factory=threading.Event)
    release: threading.Event = field(default_factory=threading.Event)


class BlockingInvoker:
    def __init__(self, state: BlockingState):
        self.state = state

    def invoke(self, *, target, arguments, idempotency_key, envelope):
        self.state.calls.append((target, arguments, idempotency_key, envelope))
        self.state.started.set()
        assert self.state.release.wait(timeout=10)
        if self.state.fail:
            raise RuntimeError("stale owner invocation failed")
        return {"ok": True, "result": {
            "kind": "tool", "content": [], "meta": {},
            "structured_content": {"value": 1},
        }}


def _runtime(config: Path, state: BlockingState) -> WorkflowRuntime:
    return WorkflowRuntime.from_config_dir(config, tool_invoker=BlockingInvoker(state))


def _thread(call):
    result: dict[str, Any] = {}
    errors: list[BaseException] = []

    def run() -> None:
        try:
            result.update(call())
        except BaseException as exc:
            errors.append(exc)

    thread = threading.Thread(target=run)
    thread.start()
    return thread, result, errors


def _effects(monkeypatch: pytest.MonkeyPatch) -> tuple[list, list]:
    transitions: list[tuple] = []
    syncs: list[tuple] = []
    monkeypatch.setattr(
        runner_module, "emit_workflow_event",
        lambda *args: transitions.append(args),
    )
    monkeypatch.setattr(runner_module, "sync_run", lambda *args: syncs.append(args))
    return transitions, syncs


@pytest.mark.parametrize("stale_failure", [False, True])
def test_reclaimed_owner_observes_and_new_owner_commits(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stale_failure: bool,
) -> None:
    config = config_dir(tmp_path, lease_seconds=1)
    old_state = BlockingState(fail=stale_failure)
    new_state = BlockingState()
    old_owner, new_owner = _runtime(config, old_state), _runtime(config, new_state)
    transitions, syncs = _effects(monkeypatch)
    old_thread, old_result, old_errors = _thread(lambda: old_owner.start_run(
        workflow_name_or_id="wf", input={}, run_key="reclaim", envelope=Envelope(),
    ))
    assert old_state.started.wait(timeout=10)
    identifier = run_id(new_owner, "reclaim")
    assert new_owner.durable_storage is not None
    original_claim = new_owner.durable_storage.claim_task

    def reclaim_later(*, run, step, inputs, now):
        return original_claim(
            run=run, step=step, inputs=inputs, now=now + timedelta(seconds=2),
        )

    new_owner.durable_storage.claim_task = reclaim_later  # type: ignore[method-assign]
    new_thread, new_result, new_errors = _thread(lambda: new_owner.resume_run(
        run_id=identifier, envelope=Envelope(),
    ))
    assert new_state.started.wait(timeout=10)
    old_state.release.set()
    old_thread.join(timeout=10)
    assert not old_thread.is_alive()
    assert old_errors == [] and old_result["status"] == "running"
    assert transitions == [] and syncs == []
    new_state.release.set()
    new_thread.join(timeout=10)
    assert not new_thread.is_alive()
    assert new_errors == [] and new_result["status"] == "succeeded"
    assert len(transitions) == len(syncs) == 1
    attempts = new_owner.durable_storage.list_task_attempts(run_id=identifier)
    assert len(attempts) == 1
    assert attempts[0]["status"] == "succeeded" and attempts[0]["revision"] == 2
    assert old_state.calls[0][2] == new_state.calls[0][2] == attempts[0]["attempt_id"]
    final = new_owner.storage.get_run(run_id=identifier)
    assert final is not None and final.status == "succeeded" and final.error is None


def test_busy_observer_has_no_transition_or_sync(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = config_dir(tmp_path)
    state = BlockingState()
    owner, observer = _runtime(config, state), _runtime(config, BlockingState())
    transitions, syncs = _effects(monkeypatch)
    thread, result, errors = _thread(lambda: owner.start_run(
        workflow_name_or_id="wf", input={}, run_key="busy", envelope=Envelope(),
    ))
    assert state.started.wait(timeout=10)
    identifier = run_id(observer, "busy")
    observed = observer.resume_run(run_id=identifier, envelope=Envelope())
    assert observed["status"] == "running"
    assert transitions == [] and syncs == []
    state.release.set()
    thread.join(timeout=10)
    assert not thread.is_alive() and errors == [] and result["status"] == "succeeded"
    assert len(transitions) == len(syncs) == 1


def test_non_fencing_value_error_is_not_observed() -> None:
    class UnusedDurable:
        def list_task_attempts(self, **kwargs):
            raise AssertionError("non-fencing errors must not query observer state")

    with pytest.raises(ValueError, match="durable completion conflict"):
        attempt_after_stale_fence(
            UnusedDurable(),  # type: ignore[arg-type]
            run_id="run", attempt_id="attempt",
            error=ValueError("durable completion conflict"),
            expected="stale task completion",
        )
