"""Deterministic completion/cancellation race regressions."""
from __future__ import annotations

import sqlite3
import threading
from pathlib import Path
from typing import Any

from factory.workflow.runtime.envelope import Envelope
from .terminal_race_support import (
    InvokeState, config_dir, gate_update, run_id, run_threads, runtime,
)


def test_completion_wins_stale_cancel_without_side_effects(tmp_path: Path) -> None:
    config = config_dir(tmp_path)
    state = InvokeState(release=threading.Event())
    owner, cancelling = runtime(config, state), runtime(config, state)
    owner_result: dict[str, Any] = {}
    owner_done = threading.Event()

    def start() -> None:
        owner_result.update(owner.start_run(
            workflow_name_or_id="wf", input={}, run_key="completion", envelope=Envelope(),
        ))
        owner_done.set()

    owner_thread = threading.Thread(target=start)
    owner_thread.start()
    assert state.started.wait(timeout=10)
    identifier = run_id(cancelling, "completion")
    original = cancelling.storage.update_run
    cancel_ready = threading.Event()

    def stale_cancel(**kwargs):
        cancel_ready.set()
        assert owner_done.wait(timeout=10)
        return original(**kwargs)

    cancelling.storage.update_run = stale_cancel  # type: ignore[method-assign]
    assert cancelling.durable_storage is not None
    side_effects = 0
    cancel_attempts = cancelling.durable_storage.cancel_task_attempts

    def counted_cancel(**kwargs):
        nonlocal side_effects
        side_effects += 1
        return cancel_attempts(**kwargs)

    cancelling.durable_storage.cancel_task_attempts = counted_cancel
    cancelled: dict[str, Any] = {}
    cancel_thread = threading.Thread(target=lambda: cancelled.update(
        cancelling.cancel_run(run_id=identifier, reason="late", envelope=Envelope())
    ))
    cancel_thread.start()
    assert cancel_ready.wait(timeout=10)
    assert state.release is not None
    state.release.set()
    owner_thread.join(timeout=10)
    cancel_thread.join(timeout=10)
    assert not owner_thread.is_alive() and not cancel_thread.is_alive()
    assert owner_result["status"] == cancelled["status"] == "succeeded"
    assert side_effects == 0
    with sqlite3.connect(config / "state.db") as conn:
        count = conn.execute(
            "SELECT count(*) FROM events WHERE event_type='system.run_cancelled'"
        ).fetchone()[0]
    assert count == 0


def test_two_cancellers_win_once_and_owner_observes_cancelled(tmp_path: Path) -> None:
    config = config_dir(tmp_path)
    state = InvokeState(release=threading.Event())
    owner = runtime(config, state)
    owner_result: dict[str, Any] = {}
    owner_thread = threading.Thread(target=lambda: owner_result.update(owner.start_run(
        workflow_name_or_id="wf", input={}, run_key="cancel", envelope=Envelope(),
    )))
    owner_thread.start()
    assert state.started.wait(timeout=10)
    callers = [runtime(config, state), runtime(config, state)]
    identifier = run_id(callers[0], "cancel")
    barrier, side_effects = threading.Barrier(2), []
    for caller in callers:
        gate_update(caller, barrier, "cancelled")
        assert caller.durable_storage is not None
        original = caller.durable_storage.cancel_task_attempts

        def counted(original=original, **kwargs):
            side_effects.append(kwargs)
            return original(**kwargs)

        caller.durable_storage.cancel_task_attempts = counted
    results = run_threads([
        lambda caller=caller: caller.cancel_run(
            run_id=identifier, reason="stop", envelope=Envelope(),
        ) for caller in callers
    ])
    assert state.release is not None
    state.release.set()
    owner_thread.join(timeout=10)
    assert not owner_thread.is_alive()
    assert [result["status"] for result in results] == ["cancelled", "cancelled"]
    assert owner_result["status"] == "cancelled" and len(side_effects) == 1
    with sqlite3.connect(config / "state.db") as conn:
        events = conn.execute(
            "SELECT count(*) FROM events WHERE event_type='system.run_cancelled'"
        ).fetchone()[0]
        attempts = conn.execute("SELECT status FROM task_attempts").fetchall()
    assert events == 1 and attempts == [("cancelled",)]
