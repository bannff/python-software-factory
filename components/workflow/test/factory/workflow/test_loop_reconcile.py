from __future__ import annotations

import hashlib
from datetime import datetime, timezone

import pytest

from factory.mcp_utils.interface import get_service, set_service
from factory.workflow.runtime.envelope import Envelope, FrozenEnvelope
from factory.workflow.runtime.loop_lifecycle import LoopLifecycle
from factory.workflow.runtime.loop_models import CycleState, LoopKind, LoopRecord, LoopState
from factory.workflow.runtime.loop_reconcile import reconcile_cycles
from factory.workflow.runtime.storage.sqlite import SqliteWorkflowStorage


def _setup(tmp_path, disposition: str, *, max_cycles: int = 3, owner: str = "owner"):
    storage = SqliteWorkflowStorage(tmp_path / "workflow.db")
    storage.init_schema()
    now = datetime.now(timezone.utc)
    loop = LoopRecord(
        tenant_id="tenant", owner_id="owner", loop_id="goal_1",
        origin_session_id="session", origin_thread_id="thread", agent_id="developer",
        kind=LoopKind.GOAL, objective="advance", cycle_instructions="act",
        interval_seconds=60, max_cycles=max_cycles, project_root=str(tmp_path),
        project_root_digest=hashlib.sha256(str(tmp_path).encode()).hexdigest(),
        created_at=now, updated_at=now,
        initiation_envelope=FrozenEnvelope(
            tenant_id="tenant", principal_id="owner", session_id="thread",
        ),
    )
    loop, cycle = LoopLifecycle(storage).start(loop)
    cycle = storage.set_cycle_state(cycle, CycleState.SCHEDULED, None, cycle.revision)
    run = storage.create_run(
        run_id="child-1", run_key="child-key", workflow_id="child",
        workflow_version=1, tenant_id="tenant",
        input={"launch_metadata": {
            "kind": "workflow_loop_cycle", "loop_id": "goal_1", "loop_cycle": "1",
        }},
        envelope=Envelope(tenant_id="tenant", principal_id=owner, session_id="thread"),
        now=now,
    )
    report = {
        "disposition": disposition, "summary": f"cycle {disposition}",
        "blocker": "needs owner" if disposition == "blocked" else None,
        "evidence": ["test"],
    }
    storage.update_run(
        run_id=run.run_id, status="succeeded", current_step_id=None,
        waiting_for_event_type=None, last_event_id=None,
        result={"task_result": {"result": {
            "structured_outputs": {"developer": report},
        }}}, error=None, now=now,
    )
    return storage, loop, cycle


def _scheduler(run_id: str = "child-1"):
    return lambda caller: lambda target, **kwargs: {
        "ok": True, "result": {"structured_content": {"ok": True, "data": {
            "fire": {"workflow_run_id": run_id, "state": "enrolled"},
        }}},
    }


@pytest.mark.asyncio
async def test_continue_settles_once_and_creates_next_cycle(tmp_path) -> None:
    storage, _, _ = _setup(tmp_path, "continue")
    previous = get_service("tool_invoker_for_caller")
    set_service("tool_invoker_for_caller", _scheduler())
    try:
        assert await reconcile_cycles(storage, tmp_path) == ("child-1",)
        assert await reconcile_cycles(storage, tmp_path) == ()
    finally:
        set_service("tool_invoker_for_caller", previous)
    loop = storage.get_loop("tenant", "owner", "goal_1")
    first = storage.get_cycle("tenant", "owner", "goal_1", 1)
    second = storage.get_cycle("tenant", "owner", "goal_1", 2)
    assert loop.last_settled_cycle == 1 and loop.next_cycle == 2
    assert first.state is CycleState.SETTLED
    assert second.state is CycleState.PENDING


@pytest.mark.asyncio
@pytest.mark.parametrize("disposition,state,reason", [
    ("success", LoopState.SUCCEEDED, "goal_complete"),
    ("blocked", LoopState.BLOCKED, "agent_blocked"),
])
async def test_terminal_reports_settle_without_next_cycle(
    tmp_path, disposition, state, reason,
) -> None:
    storage, _, _ = _setup(tmp_path, disposition)
    set_service("tool_invoker_for_caller", _scheduler())
    assert await reconcile_cycles(storage, tmp_path) == ("child-1",)
    loop = storage.get_loop("tenant", "owner", "goal_1")
    assert loop.state is state and loop.terminal_reason == reason
    assert storage.get_cycle("tenant", "owner", "goal_1", 2) is None
    if disposition == "blocked":
        assert loop.blocker_digest is not None
        assert loop.blocker_projected is True
        digest = loop.blocker_digest
        assert await reconcile_cycles(storage, tmp_path) == ()
        assert storage.get_loop("tenant", "owner", "goal_1").blocker_digest == digest


@pytest.mark.asyncio
async def test_cycle_cap_halts_without_admitting_extra_cycle(tmp_path) -> None:
    storage, _, _ = _setup(tmp_path, "continue", max_cycles=1)
    set_service("tool_invoker_for_caller", _scheduler())
    await reconcile_cycles(storage, tmp_path)
    loop = storage.get_loop("tenant", "owner", "goal_1")
    assert loop.state is LoopState.EXHAUSTED
    assert loop.terminal_reason == "cycle_cap"
    assert storage.get_cycle("tenant", "owner", "goal_1", 2) is None


@pytest.mark.asyncio
async def test_child_owner_mismatch_fails_closed(tmp_path) -> None:
    storage, _, _ = _setup(tmp_path, "success", owner="other")
    set_service("tool_invoker_for_caller", _scheduler())
    with pytest.raises(RuntimeError, match="authority mismatch"):
        await reconcile_cycles(storage, tmp_path)
    cycle = storage.get_cycle("tenant", "owner", "goal_1", 1)
    assert cycle.state is CycleState.RUNNING


@pytest.mark.asyncio
async def test_success_on_final_allowed_cycle_remains_success(tmp_path) -> None:
    storage, _, _ = _setup(tmp_path, "success", max_cycles=1)
    set_service("tool_invoker_for_caller", _scheduler())
    await reconcile_cycles(storage, tmp_path)
    loop = storage.get_loop("tenant", "owner", "goal_1")
    assert loop.state is LoopState.SUCCEEDED
    assert loop.terminal_reason == "goal_complete"
    assert storage.get_cycle("tenant", "owner", "goal_1", 2) is None


@pytest.mark.asyncio
async def test_settled_cycle_reward_recovers_after_dispatch_loss(tmp_path) -> None:
    storage, _, _ = _setup(tmp_path, "success")
    score_calls = 0

    def factory(_caller):
        def invoke(target, **kwargs):
            nonlocal score_calls
            if target["brick_name"] == "scheduler":
                return {"ok": True, "result": {"structured_content": {
                    "ok": True, "data": {"fire": {
                        "workflow_run_id": "child-1", "state": "enrolled",
                    }},
                }}}
            if target["tool_name"] != "events_score_dev_loop_cycle":
                return {"ok": True, "result": {"structured_content": {
                    "ok": True, "data": {"event_id": "projection"},
                }}}
            score_calls += 1
            if score_calls <= 2:
                return {"ok": False, "error": {"type": "Unavailable"}}
            return {"ok": True, "result": {"structured_content": {
                "ok": True, "data": {"scored": True, "reward": {
                    "idempotency_key": "reward:goal_1:1",
                }},
            }}}
        return invoke

    previous = get_service("tool_invoker_for_caller")
    set_service("tool_invoker_for_caller", factory)
    try:
        assert await reconcile_cycles(storage, tmp_path) == ("child-1",)
        events = storage.get_events_since(run_id="child-1", after_event_id=0)
        assert not any(e.event_type == "system.dev_loop_reward_dispatched" for e in events)
        assert await reconcile_cycles(storage, tmp_path) == ()
        events = storage.get_events_since(run_id="child-1", after_event_id=0)
        assert sum(e.event_type == "system.dev_loop_reward_dispatched" for e in events) == 1
        assert await reconcile_cycles(storage, tmp_path) == ()
        assert score_calls == 3
    finally:
        set_service("tool_invoker_for_caller", previous)
