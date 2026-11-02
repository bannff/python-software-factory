"""A fire whose dispatch fails must settle as failed, never block the tick."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from factory.mcp_utils.interface import get_service, set_service
from factory.scheduler.runtime.adapters.sql import SQLScheduleStore
from factory.scheduler.runtime.fire_dispatch import replay_claimed
from factory.scheduler.runtime.lifecycle import SchedulerLifecycle
from factory.storage.interface import StorageRuntime


def _lifecycle(path) -> SchedulerLifecycle:
    sql = StorageRuntime().get_sql_store("sqlite", db_path=str(path))
    return SchedulerLifecycle(SQLScheduleStore(sql))


def _claim(lifecycle, schedule_id: str):
    schedule = lifecycle.create(
        "tenant", "owner", "session", "thread", "developer", "work",
        "interval", interval_seconds=60, schedule_id=schedule_id,
    )
    return lifecycle.claim(schedule, datetime.now(timezone.utc))[1]


def _invoker(poisoned_task: str):
    def factory(_caller):
        def invoke(target, **kwargs):
            if kwargs["arguments"]["agent_id"] == poisoned_task:
                return {"ok": True, "result": {"structured_content": {"ok": False}}}
            return {"ok": True, "result": {"structured_content": {
                "ok": True, "data": {"run_id": "run-ok", "status": "running"}}}}
        return invoke
    return factory


@pytest.mark.asyncio
async def test_poisoned_claimed_fire_is_failed_and_does_not_block_the_next(tmp_path) -> None:
    lifecycle = _lifecycle(tmp_path / "s.db")
    poisoned = lifecycle.create(
        "tenant", "owner", "session", "thread", "ghost-agent", "work",
        "interval", interval_seconds=60, schedule_id="bad",
    )
    lifecycle.claim(poisoned, datetime.now(timezone.utc))
    _claim(lifecycle, "good")
    previous = get_service("tool_invoker_for_caller")
    set_service("tool_invoker_for_caller", _invoker("ghost-agent"))
    try:
        assert await replay_claimed(lifecycle) == ("run-ok",)
    finally:
        set_service("tool_invoker_for_caller", previous)
    assert lifecycle.store.get_fire("tenant", "owner", "bad", 1).state.value == "failed"
    assert lifecycle.store.get_fire("tenant", "owner", "good", 1).state.value == "enrolled"
    assert lifecycle.store.list_claimed() == []
