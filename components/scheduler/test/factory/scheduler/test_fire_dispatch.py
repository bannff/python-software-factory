from __future__ import annotations

from datetime import datetime, timezone

import pytest

from factory.mcp_utils.interface import get_service, set_service
from factory.scheduler.runtime.adapters.sql import SQLScheduleStore
from factory.scheduler.runtime.fire_dispatch import replay_claimed
from factory.scheduler.runtime.lifecycle import SchedulerLifecycle
from factory.storage.interface import StorageRuntime


def _runtime(path: str) -> SchedulerLifecycle:
    sql = StorageRuntime().get_sql_store("sqlite", db_path=path)
    return SchedulerLifecycle(SQLScheduleStore(sql))


@pytest.mark.asyncio
async def test_claimed_fire_enrolls_agent_once_with_persisted_identity(tmp_path) -> None:
    lifecycle = _runtime(str(tmp_path / "scheduler.db"))
    schedule = lifecycle.create(
        "tenant", "owner", "session", "thread", "developer", "scheduled work",
        "interval", interval_seconds=60, schedule_id="job",
    )
    _, fire = lifecycle.claim(schedule, datetime.now(timezone.utc))
    calls = []

    def factory(caller):
        assert caller == "scheduler"
        def invoke(target, **kwargs):
            calls.append((target, kwargs))
            return {"ok": True, "result": {"structured_content": {
                "ok": True, "data": {"run_id": "workflow-run-1", "status": "succeeded"},
            }}}
        return invoke

    previous = get_service("tool_invoker_for_caller")
    set_service("tool_invoker_for_caller", factory)
    try:
        assert await replay_claimed(lifecycle) == ("workflow-run-1",)
        assert await replay_claimed(lifecycle) == ()
    finally:
        set_service("tool_invoker_for_caller", previous)
    assert len(calls) == 1
    target, invocation = calls[0]
    assert target == {"brick_name": "agent", "tool_name": "spawn_background"}
    assert invocation["arguments"]["launch_id"] == fire.launch_id
    assert invocation["envelope"] == {
        "tenant_id": "tenant", "principal_id": "owner",
        "session_id": "thread", "thread_id": "thread",
    }
    persisted = lifecycle.store.get_fire("tenant", "owner", "job", 1)
    assert persisted.state.value == "enrolled"
    assert persisted.workflow_run_id == "workflow-run-1"


@pytest.mark.asyncio
async def test_reconstructed_scheduler_replays_same_claimed_launch_id(tmp_path) -> None:
    path = str(tmp_path / "restart.db")
    first = _runtime(path)
    schedule = first.create(
        "tenant", "owner", "session", "thread", "developer", "work",
        "one_shot", one_shot_at=datetime.now(timezone.utc), schedule_id="once",
    )
    _, fire = first.claim(schedule, datetime.now(timezone.utc))
    seen = []
    previous = get_service("tool_invoker_for_caller")
    set_service("tool_invoker_for_caller", lambda caller: lambda target, **kwargs: (
        seen.append(kwargs["arguments"]["launch_id"]) or
        {"ok": True, "result": {"structured_content": {
            "ok": True, "data": {"run_id": "same-run", "status": "succeeded"},
        }}}
    ))
    try:
        assert await replay_claimed(_runtime(path)) == ("same-run",)
    finally:
        set_service("tool_invoker_for_caller", previous)
    assert seen == [fire.launch_id]


@pytest.mark.asyncio
async def test_tick_claims_due_one_shot_and_enrolls_once(tmp_path) -> None:
    from factory.scheduler.runtime.runtime import SchedulerRuntime

    lifecycle = _runtime(str(tmp_path / "tick.db"))
    lifecycle.create(
        "tenant", "owner", "session", "thread", "developer", "work",
        "one_shot", one_shot_at=datetime.now(timezone.utc), schedule_id="due",
    )
    calls = []
    previous = get_service("tool_invoker_for_caller")
    def factory(caller):
        def invoke(target, **kwargs):
            arguments = kwargs["arguments"]
            if target["brick_name"] == "agent":
                calls.append(arguments["launch_id"])
                data = {"run_id": "due-run", "status": "running"}
            else:
                data = {"run_id": "due-run", "status": "succeeded"}
            return {"ok": True, "result": {"structured_content": {
                "ok": True, "data": data,
            }}}
        return invoke
    set_service("tool_invoker_for_caller", factory)
    try:
        runtime = SchedulerRuntime(lifecycle)
        assert await runtime.tick() == ("due-run",)
        assert await runtime.tick() == ()
        observed = lifecycle.store.get_fire("tenant", "owner", "due", 1)
        assert observed.state.value == "succeeded"
    finally:
        set_service("tool_invoker_for_caller", previous)
    assert calls == ["sched_due_1"]


@pytest.mark.asyncio
async def test_manual_trigger_claims_and_enrolls_once(tmp_path) -> None:
    from factory.scheduler.runtime.runtime import SchedulerRuntime

    lifecycle = _runtime(str(tmp_path / "manual.db"))
    schedule = lifecycle.create(
        "tenant", "owner", "session", "thread", "developer", "work",
        "interval", interval_seconds=3600, schedule_id="manual",
    )
    calls = []
    previous = get_service("tool_invoker_for_caller")
    set_service("tool_invoker_for_caller", lambda caller: lambda target, **kwargs: (
        calls.append(kwargs["arguments"]["launch_id"]) or
        {"ok": True, "result": {"structured_content": {
            "ok": True, "data": {"run_id": "manual-run", "status": "succeeded"},
        }}}
    ))
    try:
        fire = await SchedulerRuntime(lifecycle).trigger(
            "tenant", "owner", "manual", schedule.revision,
        )
    finally:
        set_service("tool_invoker_for_caller", previous)
    assert fire.workflow_run_id == "manual-run"
    assert calls == ["sched_manual_1"]
