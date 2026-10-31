"""Fresh S2 tests (epic #124): supervision command barriers on a live session.

A real TrainingLifecycleCoordinator session's runner consumes pause /
stop-at-checkpoint / resume intents at its barrier ticks while the issuing
thread dispatches them mid-flight. Reuses the phase-2 EventRecorder fixture
via relative import.
"""
from __future__ import annotations

import threading
import time
from unittest.mock import patch

from pydantic import BaseModel

from factory.machine_learning.runtime.adapters.local_can_lifecycle import (
    LocalCanLifecycleStore,
)
from factory.machine_learning.runtime.training_lifecycle_coordinator import (
    TrainingLifecycleCoordinator,
)
from factory.machine_learning.runtime.supervision_intents import (
    SupervisionConflictError,
    consume_supervision_intent, issue_supervision_intent,
    pending_supervision_intents,
)
from .test_phase2_training_events import EventRecorder

_OP = "ml.train-can-portfolio@v1"
_SELF = {"self": _OP}
_ACTIONS = ("pause", "stop", "resume")


class _Result(BaseModel):
    can_ids: list[str]


def test_barriers_dispatch_pause_stop_resume_mid_flight(tmp_path) -> None:
    """Issued commands reach the runner's very-next barrier tick; run survives."""
    store = LocalCanLifecycleStore(tmp_path)
    consumed, progress = [], threading.Semaphore(0)
    started = threading.Event()

    def runner(_context):
        started.set()
        for action in _ACTIONS:
            deadline = time.monotonic() + 5
            got = consume_supervision_intent(store, _OP, "a1", action)
            while got is None:
                assert time.monotonic() < deadline, f"barrier lost {action}"
                time.sleep(0.002)
                got = consume_supervision_intent(store, _OP, "a1", action)
            consumed.append(got["output"])
            progress.release()
        return {"can_ids": ["c1"]}

    with patch(
        "factory.mcp_utils.registry._services", {"tool_invoker": EventRecorder()},
    ):
        outcome: list[dict] = []
        thread = threading.Thread(target=lambda: outcome.append(
            TrainingLifecycleCoordinator(store).run(
                _OP, {"attempt_id": "a1"}, _SELF, runner, _Result,
            )
        ))
        thread.start()
        assert started.wait(5)
        intents = []
        for index, action in enumerate(_ACTIONS):
            if index:
                assert progress.acquire(timeout=5)
            issued = issue_supervision_intent(
                store, _OP, "a1", action,
                {"reason": "metric stall"} if action != "stop"
                else {"checkpoint_name": "ck1"},
            )
            assert issued["status"] == "pending"
            intents.append(issued)
        thread.join(10)
    assert not thread.is_alive()
    assert outcome[0]["status"] == "completed"
    assert [(row["action"], row["status"]) for row in consumed] == [
        ("pause", "dispatched"), ("stop", "dispatched"), ("resume", "dispatched"),
    ]
    assert consumed[1]["command"] == {"attempt_id": "a1", "checkpoint_name": "ck1"}


def test_consume_replays_one_dispatch_across_barrier_ticks(tmp_path) -> None:
    """A dispatched command replays its receipt at later ticks, no new state."""
    store = LocalCanLifecycleStore(tmp_path)
    claim, _ = store.claim(_OP, "r1", "b" * 64)
    assert claim == "created"
    issue_supervision_intent(store, _OP, "r1", "pause", {"reason": "x"})
    first = consume_supervision_intent(store, _OP, "r1", "pause")
    replay = consume_supervision_intent(store, _OP, "r1", "pause")
    assert first["status"] == "dispatched" and replay["status"] == "replayed"
    assert first["output"] == replay["output"]
    assert replay["output"]["action"] == "pause"
    rows = pending_supervision_intents(store, _OP, "r1")
    assert rows == [{
        "action": "pause", "intent_id": rows[0]["intent_id"],
        "intent_sha256": first["intent_sha256"],
        "inputs": {"attempt_id": "r1", "reason": "x"},
        "status": "dispatched",
    }]


def test_concurrent_divergent_issuance_stays_typed(tmp_path) -> None:
    """Concurrent divergent pauses serialize on the effect scope.

    Exactly one issuance wins (``pending``); every loser surfaces the typed
    :class:`SupervisionConflictError`. No bare ``ValueError`` escapes from the
    immutable-effect publish window — the lock-free failure mode the runner
    turned into a FAILED terminal for a live run.
    """
    store = LocalCanLifecycleStore(tmp_path)
    claim, _ = store.claim(_OP, "a1", "b" * 64)
    assert claim == "created"
    workers = 8
    barrier = threading.Barrier(workers)
    outcomes: list[object] = []
    guard = threading.Lock()

    def issue(index: int) -> None:
        barrier.wait()
        try:
            result: object = issue_supervision_intent(
                store, _OP, "a1", "pause", {"reason": f"stall-{index}"},
            )
        except ValueError as exc:  # includes SupervisionConflictError
            result = exc
        with guard:
            outcomes.append(result)

    threads = [threading.Thread(target=issue, args=(index,)) for index in range(workers)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(10)
    assert all(not thread.is_alive() for thread in threads)
    assert len(outcomes) == workers
    winners = [row for row in outcomes if isinstance(row, dict)]
    losers = [row for row in outcomes if isinstance(row, BaseException)]
    assert len(winners) == 1 and winners[0]["status"] == "pending"
    assert len(losers) == workers - 1
    assert all(isinstance(exc, SupervisionConflictError) for exc in losers)
