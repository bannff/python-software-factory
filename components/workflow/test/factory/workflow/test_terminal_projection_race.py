"""Idempotent journal-to-run terminal projection regression."""
from __future__ import annotations

import threading
from datetime import datetime, timezone
from pathlib import Path

import pytest

import factory.workflow.runtime.execution.runner as runner_module
from factory.workflow.runtime.envelope import Envelope
from .terminal_race_support import (
    InvokeState, config_dir, gate_update, run_id, run_threads, runtime,
)


class ProjectionCrash(BaseException):
    pass


def test_two_callers_project_one_succeeded_journal_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    config, state = config_dir(tmp_path), InvokeState()
    crashed = runtime(config, state)
    original = crashed.storage.update_run

    def stop_projection(**kwargs):
        if kwargs["status"] == "succeeded":
            raise ProjectionCrash()
        return original(**kwargs)

    crashed.storage.update_run = stop_projection  # type: ignore[method-assign]
    with pytest.raises(ProjectionCrash):
        crashed.start_run(
            workflow_name_or_id="wf", input={}, run_key="projection", envelope=Envelope(),
        )
    identifier = run_id(crashed, "projection")
    transitions: list[tuple] = []
    syncs: list[tuple] = []
    monkeypatch.setattr(
        runner_module, "emit_workflow_event",
        lambda *args: transitions.append(args),
    )
    monkeypatch.setattr(
        runner_module, "sync_run", lambda *args: syncs.append(args),
    )
    callers = [runtime(config, state), runtime(config, state)]
    barrier = threading.Barrier(2)
    for caller in callers:
        gate_update(caller, barrier, "succeeded")
    results = run_threads([
        lambda caller=caller: caller.resume_run(
            run_id=identifier, envelope=Envelope(),
        ) for caller in callers
    ])
    assert [result["status"] for result in results] == ["succeeded", "succeeded"]
    final = callers[0].storage.get_run(run_id=identifier)
    assert final is not None and final.revision == 1
    assert final.result == {"ok": True, "task_result": {"value": 1}}
    assert len(state.calls) == 1
    assert len(transitions) == 1
    assert transitions[0][0] == "workflow.step_transition"
    assert len(syncs) == 1


def test_dispatch_error_loser_has_empty_state_delta(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = config_dir(tmp_path)
    loser = runtime(config, InvokeState())
    now = datetime.now(timezone.utc)
    record = loser.storage.create_run(
        run_id="dispatch-race", workflow_id="wf", workflow_version=1,
        tenant_id=None, input={}, envelope=Envelope(), now=now,
    )
    entered, release = threading.Event(), threading.Event()

    def stale_dispatch(*args, **kwargs):
        entered.set()
        assert release.wait(timeout=10)
        raise RuntimeError("late dispatch failure")

    loser.runner._dispatch = stale_dispatch  # type: ignore[method-assign]
    events: list[tuple] = []
    syncs: list[tuple] = []
    monkeypatch.setattr(runner_module, "emit_workflow_event", lambda *args: events.append(args))
    monkeypatch.setattr(runner_module, "sync_run", lambda *args: syncs.append(args))
    thread, result, errors = run_threads_with_result(lambda: loser.runner.step_run(
        run_id=record.run_id, envelope=Envelope(), max_transitions=1,
    ))
    assert entered.wait(timeout=10)
    loser.storage.update_run(
        run_id=record.run_id, status="succeeded", current_step_id="work",
        waiting_for_event_type=None, last_event_id=None, result={"winner": True},
        error=None, now=now, expected_statuses={"running"},
        expected_revision=record.revision,
    )
    release.set()
    thread.join(timeout=10)
    assert not thread.is_alive() and errors == []
    assert result == {
        "status": "succeeded", "state_delta": {"transitions": []},
    }
    assert events == [] and syncs == []


def run_threads_with_result(call):
    result: dict = {}
    errors: list[BaseException] = []

    def run() -> None:
        try:
            result.update(call())
        except BaseException as exc:
            errors.append(exc)

    thread = threading.Thread(target=run)
    thread.start()
    return thread, result, errors
