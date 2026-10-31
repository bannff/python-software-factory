"""Retry-aware stale-owner regressions across two workflow runtimes."""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest

import factory.workflow.runtime.execution.runner as runner_module
from factory.workflow.runtime.envelope import Envelope
from factory.workflow.runtime.runtime import WorkflowRuntime
from factory.workflow.runtime.task_ids import task_attempt_id
from .terminal_race_support import config_dir, run_id


@dataclass
class OwnerState:
    fail: bool
    started: threading.Event = field(default_factory=threading.Event)
    release: threading.Event = field(default_factory=threading.Event)


class StaleOwnerInvoker:
    def __init__(self, state: OwnerState):
        self.state = state

    def invoke(self, **kwargs):
        self.state.started.set()
        assert self.state.release.wait(timeout=10)
        if self.state.fail:
            raise RuntimeError("stale owner invocation failed")
        return _success()


@dataclass
class RetryState:
    calls: list[str] = field(default_factory=list)
    second_started: threading.Event = field(default_factory=threading.Event)
    release: threading.Event = field(default_factory=threading.Event)
    final_effects: int = 0


class RetryThenSuccessInvoker:
    def __init__(self, state: RetryState):
        self.state = state

    def invoke(self, *, idempotency_key, **kwargs):
        self.state.calls.append(idempotency_key)
        if len(self.state.calls) == 1:
            return {"ok": False, "error": {
                "type": "ServiceUnavailable", "message": "temporarily unavailable",
            }}
        self.state.second_started.set()
        assert self.state.release.wait(timeout=10)
        self.state.final_effects += 1
        return _success()


def _success() -> dict[str, Any]:
    return {"ok": True, "result": {
        "kind": "tool", "content": [], "meta": {},
        "structured_content": {"value": 1},
    }}


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


@pytest.mark.parametrize("stale_failure", [False, True])
def test_retry_attempt_is_authoritative_over_stale_owner(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stale_failure: bool,
) -> None:
    config = config_dir(tmp_path, lease_seconds=1, max_attempts=2)
    owner_state, retry_state = OwnerState(stale_failure), RetryState()
    owner = WorkflowRuntime.from_config_dir(
        config, tool_invoker=StaleOwnerInvoker(owner_state),
    )
    retrier = WorkflowRuntime.from_config_dir(
        config, tool_invoker=RetryThenSuccessInvoker(retry_state),
    )
    transitions: list[tuple] = []
    syncs: list[tuple] = []
    monkeypatch.setattr(runner_module, "emit_workflow_event", lambda *args: transitions.append(args))
    monkeypatch.setattr(runner_module, "sync_run", lambda *args: syncs.append(args))

    owner_thread, owner_result, owner_errors = _thread(lambda: owner.start_run(
        workflow_name_or_id="wf", input={}, run_key="retry-stale", envelope=Envelope(),
    ))
    assert owner_state.started.wait(timeout=10)
    identifier = run_id(retrier, "retry-stale")
    assert retrier.durable_storage is not None
    original_claim = retrier.durable_storage.claim_task

    def expired_claim(*, run, step, inputs, now):
        return original_claim(
            run=run, step=step, inputs=inputs, now=now + timedelta(seconds=2),
        )

    retrier.durable_storage.claim_task = expired_claim  # type: ignore[method-assign]
    retry_thread, retry_result, retry_errors = _thread(lambda: retrier.resume_run(
        run_id=identifier, envelope=Envelope(),
    ))
    assert retry_state.second_started.wait(timeout=10)

    owner_state.release.set()
    owner_thread.join(timeout=10)
    assert not owner_thread.is_alive()
    assert owner_errors == [] and owner_result["status"] == "running"
    assert all(event[1].get("status") != "failed" for event in transitions)

    retry_state.release.set()
    retry_thread.join(timeout=10)
    assert not retry_thread.is_alive()
    assert retry_errors == [] and retry_result["status"] == "succeeded"
    attempts = retrier.durable_storage.list_task_attempts(run_id=identifier)
    assert [attempt["attempt_number"] for attempt in attempts] == [1, 2]
    assert attempts[0]["attempt_id"] == task_attempt_id(attempts[0]["step_execution_id"], 1)
    assert attempts[1]["attempt_id"] == task_attempt_id(attempts[1]["step_execution_id"], 2)
    assert attempts[0]["attempt_id"] != attempts[1]["attempt_id"]
    assert retry_state.calls == [attempts[0]["attempt_id"], attempts[1]["attempt_id"]]
    assert retry_state.final_effects == 1
    assert len([event for event in transitions if event[1].get("status") == "succeeded"]) == 1
    assert len(syncs) == 1
    final = retrier.storage.get_run(run_id=identifier)
    assert final is not None and final.status == "succeeded" and final.error is None
