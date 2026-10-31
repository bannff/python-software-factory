"""Scheduler migration import unsafe-field and restart tests."""
from __future__ import annotations

import pytest

from factory.scheduler.runtime.adapters.sql import SQLScheduleStore
from factory.scheduler.runtime.lifecycle import SchedulerLifecycle
from factory.mcp_utils.runtime.schema_migration import SchemaMigrationError

from .test_migration_import import (
    _call, _runtime, _values,
)
from factory.storage.interface import StorageRuntime


@pytest.mark.asyncio
@pytest.mark.parametrize("unsafe", [
    {"approval_mode": "auto"}, {"script": "rm -rf /"}, {"command": "curl evil"},
    {"env": {"SECRET": "x"}}, {"channel": "slack"},
    {"delivery_mode": "workflow_loop"}, {"maintenance_target": "telemetry_retention"},
    {"result": "done"}, {"error": "boom"}, {"revision": 9},
])
async def test_unsafe_or_extra_schedule_fields_are_refused(tmp_path, unsafe):
    catalog, lifecycle = _runtime(tmp_path / "unsafe.sqlite")
    values, schedule_id = _values()
    values["schedule"] = {**values["schedule"], **unsafe}
    with pytest.raises(SchemaMigrationError):
        await _call(catalog, values)
    assert lifecycle.store.get("tenant", "owner", schedule_id) is None


@pytest.mark.asyncio
async def test_imported_paused_schedule_survives_restart(tmp_path):
    path = tmp_path / "restart.sqlite"
    catalog, _ = _runtime(path)
    values, schedule_id = _values()
    await _call(catalog, values)
    reopened = SchedulerLifecycle(
        SQLScheduleStore(StorageRuntime().get_sql_store("sqlite", db_path=str(path))),
    )
    record = reopened.store.get("tenant", "owner", schedule_id)
    assert record is not None
    assert record.state.value == "paused"
    assert record.revision == 1
    assert reopened.store.list_due(record.created_at.isoformat(), 100) == []
