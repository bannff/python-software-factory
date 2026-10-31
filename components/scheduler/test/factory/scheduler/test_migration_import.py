"""Protected Migration-to-Scheduler paused import boundary tests."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from factory.mcp_utils.interface import (
    MigrationImportBinding, ServiceOnlyAccessError, acquire_service_entry,
    begin_service_invocation, end_service_invocation,
    mint_internal_invocation_claims, reset_envelope,
    reset_internal_invocation_claims, set_envelope, set_internal_invocation_claims,
)
from factory.mcp_utils.runtime.tool_catalog import ToolCatalog
from factory.mcp_utils.runtime.schema_migration import SchemaMigrationError
from factory.scheduler.mcp.import_contracts import ImportScheduleDefinition
from factory.scheduler.runtime.adapters.sql import SQLScheduleStore
from factory.scheduler.runtime.import_records import derive_schedule_id, target_digest
from factory.scheduler.runtime.lifecycle import SchedulerLifecycle
from factory.scheduler.runtime.runtime import SchedulerRuntime
from factory.scheduler.server import create_tool_catalog
from factory.storage.interface import StorageRuntime

_NAME = "scheduler_import_record"
_BINDING_FIELDS = (
    "tenant_id", "owner_id", "source_adapter", "source_fingerprint",
    "plan_digest", "kind", "source_record_id", "target_digest",
)
_RECORD_ID = "c" * 64


def _runtime(path) -> tuple[ToolCatalog, SchedulerLifecycle]:
    sql = StorageRuntime().get_sql_store("sqlite", db_path=str(path))
    lifecycle = SchedulerLifecycle(SQLScheduleStore(sql))
    return create_tool_catalog(SchedulerRuntime(lifecycle)), lifecycle


def _definition(**overrides) -> ImportScheduleDefinition:
    fields = {
        "task": "daily digest", "agent_id": "companion-x-default",
        "kind": "cron", "cron_expression": "17 3 * * *",
    }
    fields.update(overrides)
    return ImportScheduleDefinition(**fields)


def _values(*, tenant="tenant", owner="owner", adapter="kirocrew-v1",
            record_id=_RECORD_ID, definition=None, **binding_overrides):
    definition = definition or _definition()
    definition_json = definition.model_dump(mode="json")
    schedule_id = derive_schedule_id(adapter, record_id)
    values = {
        "tenant_id": tenant, "owner_id": owner, "source_adapter": adapter,
        "source_fingerprint": "a" * 64, "plan_digest": "b" * 64,
        "kind": "schedules", "source_record_id": record_id,
        "target_digest": target_digest(tenant, owner, schedule_id, definition_json),
        "schedule": definition.model_dump(),
    }
    values.update(binding_overrides)
    return values, schedule_id


async def _call(catalog, values, *, caller="migration",
                tenant="tenant", owner="owner"):
    tool = await catalog.get_tool(_NAME)
    binding = MigrationImportBinding(**{key: values[key] for key in _BINDING_FIELDS})
    claims = mint_internal_invocation_claims(
        caller=caller, audience="scheduler", target_tool=_NAME,
        binding=binding, target=tool,
    )
    ctoken = set_internal_invocation_claims(claims)
    etoken = set_envelope(
        {"tenant_id": tenant, "principal_id": owner,
         "session_id": "migration-session", "thread_id": "thread"},
    )
    state = None
    try:
        state = begin_service_invocation(
            tool, audience="scheduler", target_tool=_NAME, arguments=values,
        )
        entry = acquire_service_entry(tool.fn)
        return await catalog.call_tool(
            _NAME, {**values, "_service_entry_authorization": entry},
        )
    finally:
        end_service_invocation(state)
        reset_internal_invocation_claims(ctoken)
        reset_envelope(etoken)


def _data(result) -> dict:
    return result.structured_content["data"]


@pytest.mark.asyncio
async def test_unauthorized_caller_is_denied_before_validation_or_effects(tmp_path):
    catalog, lifecycle = _runtime(tmp_path / "deny.sqlite")
    values, schedule_id = _values()
    with pytest.raises(ServiceOnlyAccessError):
        await _call(catalog, values, caller="intruder")
    assert lifecycle.store.get("tenant", "owner", schedule_id) is None


@pytest.mark.asyncio
async def test_exact_binding_success_persists_paused_from_first_row(tmp_path):
    catalog, lifecycle = _runtime(tmp_path / "ok.sqlite")
    values, schedule_id = _values()
    result = await _call(catalog, values)
    data = _data(result)
    assert data["imported"] is True and data["replayed"] is False
    record = lifecycle.store.get("tenant", "owner", schedule_id)
    assert record is not None
    assert record.state.value == "paused"
    assert record.next_fire_at is None
    assert record.revision == 1  # never active then paused
    assert lifecycle.store.list_due(record.created_at.isoformat(), 100) == []


@pytest.mark.asyncio
async def test_digest_mismatch_is_refused_without_effects(tmp_path):
    catalog, lifecycle = _runtime(tmp_path / "digest.sqlite")
    values, schedule_id = _values(target_digest="d" * 64)
    result = await _call(catalog, values)
    assert result.is_error
    assert result.structured_content["error"] == "scheduler_import_digest_mismatch"
    assert lifecycle.store.get("tenant", "owner", schedule_id) is None


@pytest.mark.asyncio
async def test_replay_of_same_record_is_idempotent(tmp_path):
    catalog, lifecycle = _runtime(tmp_path / "replay.sqlite")
    values, schedule_id = _values()
    first = _data(await _call(catalog, values))
    second = _data(await _call(catalog, values))
    assert first["imported"] is True and first["replayed"] is False
    assert second["imported"] is False and second["replayed"] is True
    assert second["schedule"]["revision"] == 1
    assert len(lifecycle.store.list("tenant", "owner")) == 1


@pytest.mark.asyncio
async def test_owner_isolation_scopes_imported_schedule(tmp_path):
    catalog, lifecycle = _runtime(tmp_path / "isolation.sqlite")
    values, schedule_id = _values(tenant="tenant", owner="owner-a")
    await _call(catalog, values, tenant="tenant", owner="owner-a")
    assert lifecycle.store.get("tenant", "owner-a", schedule_id) is not None
    assert lifecycle.store.get("tenant", "owner-b", schedule_id) is None
    assert lifecycle.store.list("tenant", "owner-b") == []


@pytest.mark.asyncio
async def test_authority_mismatch_between_envelope_and_binding_is_refused(tmp_path):
    catalog, lifecycle = _runtime(tmp_path / "authority.sqlite")
    values, schedule_id = _values(tenant="tenant", owner="owner")
    result = await _call(catalog, values, tenant="tenant", owner="someone-else")
    assert result.is_error
    assert result.structured_content["error"] == "scheduler_import_authority_mismatch"
    assert lifecycle.store.get("tenant", "owner", schedule_id) is None


@pytest.mark.asyncio
@pytest.mark.parametrize("definition,expected_kind", [
    (_definition(), "cron"),
    (_definition(kind="interval", cron_expression=None, interval_seconds=300),
     "interval"),
    (_definition(kind="one_shot", cron_expression=None,
                 one_shot_at=datetime(2027, 1, 1, tzinfo=timezone.utc)), "one_shot"),
])
async def test_all_three_schedule_kinds_import_paused(tmp_path, definition, expected_kind):
    catalog, lifecycle = _runtime(tmp_path / f"{expected_kind}.sqlite")
    values, schedule_id = _values(record_id=("e" * 63) + "f", definition=definition)
    result = await _call(catalog, values)
    data = _data(result)
    assert data["imported"] is True
    record = lifecycle.store.get("tenant", "owner", schedule_id)
    assert record.kind.value == expected_kind
    assert record.state.value == "paused" and record.next_fire_at is None

