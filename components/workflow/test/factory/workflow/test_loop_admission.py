from __future__ import annotations

import hashlib
from datetime import datetime, timezone

import pytest

from factory.mcp_utils.interface import get_service, set_service
from factory.workflow.runtime.envelope import FrozenEnvelope
from factory.workflow.runtime.loop_admission import admit_pending
from factory.workflow.runtime.loop_lifecycle import LoopLifecycle
from factory.workflow.runtime.loop_models import CycleState, LoopKind, LoopRecord, LoopState
from factory.workflow.runtime.storage.sqlite import SqliteWorkflowStorage


def _setup(tmp_path, *, runtime_deadline=None):
    storage = SqliteWorkflowStorage(tmp_path / "workflow.db")
    storage.init_schema()
    now = datetime.now(timezone.utc)
    record = LoopRecord(
        tenant_id="tenant", owner_id="owner", loop_id="goal_1",
        origin_session_id="session", origin_thread_id="thread",
        agent_id="developer", kind=LoopKind.GOAL,
        objective="advance work", cycle_instructions="read, act, verify",
        interval_seconds=60, project_root=str(tmp_path),
        runtime_deadline=runtime_deadline,
        project_root_digest=hashlib.sha256(str(tmp_path).encode()).hexdigest(),
        created_at=now, updated_at=now,
        initiation_envelope=FrozenEnvelope(
            tenant_id="tenant", principal_id="owner", session_id="thread",
        ),
    )
    LoopLifecycle(storage).start(record)
    return storage


@pytest.mark.asyncio
async def test_pending_cycle_admits_one_owner_bound_scheduler_one_shot(tmp_path) -> None:
    storage = _setup(tmp_path)
    calls = []
    previous = get_service("tool_invoker_for_caller")

    def factory(caller):
        def invoke(target, **kwargs):
            calls.append((caller, target, kwargs))
            args = kwargs["arguments"]
            return {"ok": True, "result": {"structured_content": {
                "ok": True, "data": {"schedule": {
                    "schedule_id": args["schedule_id"],
                    "tenant_id": "tenant", "owner_id": "owner",
                }},
            }}}
        return invoke

    set_service("tool_invoker_for_caller", factory)
    try:
        assert await admit_pending(storage, tmp_path) == ("loop_goal_1_1",)
        assert await admit_pending(storage, tmp_path) == ()
    finally:
        set_service("tool_invoker_for_caller", previous)
    assert len(calls) == 1
    caller, target, call = calls[0]
    assert caller == "workflow"
    assert target == {"brick_name": "scheduler", "tool_name": "scheduler_add"}
    assert call["envelope"]["principal_id"] == "owner"
    args = call["arguments"]
    assert args["kind"] == "one_shot"
    assert args["output_schema"] == "loop-cycle-report-v1"
    assert args["delivery_mode"] == "workflow_loop"
    cycle = storage.get_cycle("tenant", "owner", "goal_1", 1)
    assert cycle.state is CycleState.SCHEDULED


@pytest.mark.asyncio
async def test_restart_does_not_readmit_scheduled_cycle(tmp_path) -> None:
    storage = _setup(tmp_path)
    set_service("tool_invoker_for_caller", lambda caller: lambda target, **kwargs: {
        "ok": True, "result": {"structured_content": {"ok": True, "data": {
            "schedule": {"schedule_id": "loop_goal_1_1",
                         "tenant_id": "tenant", "owner_id": "owner"},
        }}},
    })
    await admit_pending(storage, tmp_path)
    restarted = SqliteWorkflowStorage(tmp_path / "workflow.db")
    restarted.init_schema()
    assert await admit_pending(restarted, tmp_path) == ()


@pytest.mark.asyncio
async def test_stop_sentinel_terminalizes_before_scheduler_call(tmp_path) -> None:
    storage = _setup(tmp_path)
    (tmp_path / ".companion-loop-stop-goal_1").touch()
    calls = []
    set_service("tool_invoker_for_caller", lambda caller: lambda target, **kwargs:
                calls.append(target))
    assert await admit_pending(storage, tmp_path) == ()
    loop = storage.get_loop("tenant", "owner", "goal_1")
    assert loop.state is LoopState.STOPPED and loop.terminal_reason == "stop_file"
    assert calls == []


@pytest.mark.asyncio
async def test_runtime_deadline_halts_before_scheduler_admission(tmp_path) -> None:
    from datetime import timedelta
    storage = _setup(
        tmp_path,
        runtime_deadline=datetime.now(timezone.utc) - timedelta(seconds=1),
    )
    calls = []
    set_service("tool_invoker_for_caller", lambda caller: lambda target, **kwargs:
                calls.append(target))
    assert await admit_pending(storage, tmp_path) == ()
    loop = storage.get_loop("tenant", "owner", "goal_1")
    assert loop.state is LoopState.EXHAUSTED
    assert loop.terminal_reason == "runtime_budget"
    assert calls == []
