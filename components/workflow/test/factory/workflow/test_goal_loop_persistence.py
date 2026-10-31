from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from hypothesis.stateful import RuleBasedStateMachine, invariant, rule

from factory.workflow.runtime.envelope import FrozenEnvelope
from factory.workflow.runtime.loop_lifecycle import LoopConflictError, LoopLifecycle
from factory.workflow.runtime.loop_models import LoopKind, LoopRecord, LoopState
from factory.workflow.runtime.loop_sentinel import sentinel_exists
from factory.workflow.runtime.loop_stopping import evaluate_stop
from factory.workflow.runtime.storage.sqlite import SqliteWorkflowStorage


def _record(root: Path, *, loop_id: str = "goal_1", max_cycles: int = 3) -> LoopRecord:
    now = datetime.now(timezone.utc)
    return LoopRecord(
        tenant_id="tenant", owner_id="owner", loop_id=loop_id,
        origin_session_id="session", origin_thread_id="thread",
        agent_id="developer", kind=LoopKind.GOAL,
        objective="advance one task", cycle_instructions="read, act, verify",
        interval_seconds=60, max_cycles=max_cycles,
        project_root=str(root),
        project_root_digest=hashlib.sha256(str(root).encode()).hexdigest(),
        created_at=now, updated_at=now,
        initiation_envelope=FrozenEnvelope(
            tenant_id="tenant", principal_id="owner", session_id="thread",
        ),
    )


def _storage(path: Path) -> SqliteWorkflowStorage:
    storage = SqliteWorkflowStorage(path)
    storage.init_schema()
    return storage


def test_loop_and_initial_cycle_are_idempotent_and_restart_safe(tmp_path) -> None:
    record = _record(tmp_path)
    lifecycle = LoopLifecycle(_storage(tmp_path / "workflow.db"))
    loop, cycle = lifecycle.start(record)
    assert lifecycle.start(record) == (loop, cycle)
    restarted = _storage(tmp_path / "workflow.db")
    assert restarted.get_loop("tenant", "owner", "goal_1") == loop
    assert restarted.get_cycle("tenant", "owner", "goal_1", 1) == cycle
    assert restarted.get_loop("tenant", "other", "goal_1") is None


def test_revision_cas_and_terminal_state_are_fenced(tmp_path) -> None:
    lifecycle = LoopLifecycle(_storage(tmp_path / "cas.db"))
    loop, _ = lifecycle.start(_record(tmp_path))
    paused = lifecycle.transition(loop, LoopState.PAUSED, loop.revision)
    assert lifecycle.store.set_loop_state(loop, LoopState.STOPPED, "stale", 1) is None
    stopped = lifecycle.transition(paused, LoopState.STOPPED, paused.revision, "user_stop")
    with pytest.raises(LoopConflictError):
        lifecycle.transition(stopped, LoopState.ACTIVE, stopped.revision)


def test_stop_order_never_buys_extra_cycle(tmp_path) -> None:
    record = _record(tmp_path, max_cycles=1).model_copy(update={
        "last_settled_cycle": 1, "next_cycle": 2,
        "runtime_deadline": datetime.now(timezone.utc) - timedelta(seconds=1),
    })
    decision = evaluate_stop(
        record, now=datetime.now(timezone.utc), sentinel_exists=True,
    )
    assert (decision.state, decision.reason) == (LoopState.STOPPED, "stop_file")
    decision = evaluate_stop(
        record, now=datetime.now(timezone.utc), sentinel_exists=False,
    )
    assert (decision.state, decision.reason) == (LoopState.EXHAUSTED, "cycle_cap")


def test_stop_sentinel_never_follows_symlink_or_escaped_root(tmp_path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    target = tmp_path / "outside"
    target.write_text("secret")
    (root / ".companion-loop-stop-goal_1").symlink_to(target)
    assert sentinel_exists("goal_1", root, tmp_path)
    with pytest.raises(RuntimeError, match="not allowed"):
        sentinel_exists("goal_1", tmp_path, root)


class LoopMachine(RuleBasedStateMachine):
    def __init__(self) -> None:
        super().__init__()
        import tempfile
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.lifecycle = LoopLifecycle(_storage(root / "state.db"))
        self.record, _ = self.lifecycle.start(_record(root))

    @rule()
    def pause_or_resume(self) -> None:
        if self.record.state is LoopState.ACTIVE:
            self.record = self.lifecycle.transition(
                self.record, LoopState.PAUSED, self.record.revision,
            )
        elif self.record.state is LoopState.PAUSED:
            self.record = self.lifecycle.transition(
                self.record, LoopState.ACTIVE, self.record.revision,
            )

    @rule()
    def stop(self) -> None:
        if self.record.state in {LoopState.ACTIVE, LoopState.PAUSED}:
            self.record = self.lifecycle.transition(
                self.record, LoopState.STOPPED, self.record.revision, "test_stop",
            )

    @invariant()
    def sequence_and_terminal_fences_hold(self) -> None:
        assert self.record.next_cycle == self.record.last_settled_cycle + 1
        if self.record.state is LoopState.STOPPED:
            with pytest.raises(LoopConflictError):
                self.lifecycle.transition(
                    self.record, LoopState.ACTIVE, self.record.revision,
                )

    def teardown(self) -> None:
        self.temp.cleanup()


TestLoopMachine = LoopMachine.TestCase
