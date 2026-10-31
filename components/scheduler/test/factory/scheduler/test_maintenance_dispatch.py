from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from factory.mcp_utils.interface import get_service, set_service
from factory.scheduler.mcp.contracts import AddScheduleInput
from factory.scheduler.runtime.adapters.sql import SQLScheduleStore
from factory.scheduler.runtime.fire_dispatch import replay_claimed
from factory.scheduler.runtime.lifecycle import SchedulerLifecycle
from factory.scheduler.runtime.runtime import (
    SchedulerRuntime, ensure_telemetry_retention_schedule,
)
from factory.storage.interface import StorageRuntime


def _lifecycle(path: str) -> SchedulerLifecycle:
    sql = StorageRuntime().get_sql_store("sqlite", db_path=path)
    return SchedulerLifecycle(SQLScheduleStore(sql))


def _maintenance(lifecycle: SchedulerLifecycle, schedule_id: str = "retention"):
    return lifecycle.create(
        "system", "system", "system-maintenance", "system-maintenance",
        "system-maintenance", "daily telemetry retention", "interval",
        interval_seconds=60, delivery_mode="maintenance",
        maintenance_target="telemetry_retention", schedule_id=schedule_id,
    )


def test_maintenance_binding_is_closed_and_not_public(tmp_path) -> None:
    lifecycle = _lifecycle(str(tmp_path / "models.db"))
    with pytest.raises(ValidationError):
        lifecycle.create(
            "t", "o", "s", "th", "agent", "task", "interval",
            interval_seconds=60, delivery_mode="maintenance",
        )
    with pytest.raises(ValidationError):
        lifecycle.create(
            "t", "o", "s", "th", "agent", "task", "interval",
            interval_seconds=60, maintenance_target="telemetry_retention",
        )
    assert "maintenance_target" not in AddScheduleInput.model_fields


def test_retention_schedule_seeder_is_restart_idempotent(tmp_path) -> None:
    path = str(tmp_path / "seed.db")
    first = ensure_telemetry_retention_schedule(SchedulerRuntime(_lifecycle(path)))
    second = ensure_telemetry_retention_schedule(SchedulerRuntime(_lifecycle(path)))
    assert first.schedule_id == second.schedule_id == "system_telemetry_retention"
    assert len(_lifecycle(path).list("system", "system")) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("tool_ok,state", [(True, "succeeded"), (False, "failed")])
async def test_maintenance_dispatch_settles_once(tmp_path, tool_ok, state) -> None:
    lifecycle = _lifecycle(str(tmp_path / f"{state}.db"))
    schedule = _maintenance(lifecycle)
    _, fire = lifecycle.claim(schedule, datetime.now(timezone.utc))
    calls = []

    def factory(caller):
        assert caller == "scheduler"
        def invoke(target, **kwargs):
            calls.append((target, kwargs))
            return {"ok": True, "result": {"structured_content": {
                "ok": tool_ok, "data": {} if tool_ok else None,
            }}}
        return invoke

    previous = get_service("tool_invoker_for_caller")
    set_service("tool_invoker_for_caller", factory)
    try:
        expected = (f"maintenance-{fire.launch_id}",)
        assert await replay_claimed(lifecycle) == expected
        assert await replay_claimed(lifecycle) == ()
    finally:
        set_service("tool_invoker_for_caller", previous)
    assert len(calls) == 1
    target, invocation = calls[0]
    assert target == {
        "brick_name": "telemetry", "tool_name": "telemetry_run_retention",
    }
    assert invocation["arguments"] == {}
    assert invocation["idempotency_key"] == f"scheduler-fire:{fire.launch_id}"
    persisted = lifecycle.store.get_fire("system", "system", "retention", 1)
    assert persisted is not None and persisted.state.value == state
