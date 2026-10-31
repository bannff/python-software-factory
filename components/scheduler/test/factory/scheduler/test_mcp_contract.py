from __future__ import annotations

import asyncio

from factory.mcp_utils.interface import (
    get_service, reset_envelope, set_envelope, set_service,
)
from factory.scheduler.runtime.adapters.sql import SQLScheduleStore
from factory.scheduler.runtime.lifecycle import SchedulerLifecycle
from factory.scheduler.runtime.runtime import SchedulerRuntime
from factory.scheduler.server import create_tool_catalog
from factory.storage.interface import StorageRuntime


def _catalog(tmp_path):
    sql = StorageRuntime().get_sql_store("sqlite", db_path=str(tmp_path / "db.sqlite"))
    lifecycle = SchedulerLifecycle(SQLScheduleStore(sql))
    lifecycle.create(
        "tenant", "owner", "session", "thread", "developer", "work",
        "interval", interval_seconds=60, schedule_id="job",
    )
    return create_tool_catalog(SchedulerRuntime(lifecycle))


def test_scheduler_tools_have_strict_typed_contracts(tmp_path) -> None:
    tools = asyncio.run(_catalog(tmp_path).list_tools())
    names = {tool.name for tool in tools}
    assert names == {
        "scheduler_get", "scheduler_list", "scheduler_get_fire",
        "scheduler_add", "scheduler_pause", "scheduler_resume", "scheduler_remove",
        "scheduler_trigger", "scheduler_import_record",
    }
    for tool in tools:
        assert tool.fn._mcp_input_model.model_json_schema()["additionalProperties"] is False
        assert tool.fn._mcp_output_model is not None


def test_scheduler_reads_and_cas_use_owner_without_thread(tmp_path) -> None:
    catalog = _catalog(tmp_path)
    tools = {tool.name: tool for tool in asyncio.run(catalog.list_tools())}
    token = set_envelope({
        "tenant_id": "tenant", "principal_id": "owner",
    })
    try:
        result = tools["scheduler_get"].fn(schedule_id="job")
        listed = tools["scheduler_list"].fn()
        paused = tools["scheduler_pause"].fn(
            schedule_id="job", expected_revision=1,
        )
    finally:
        reset_envelope(token)
    assert result.ok is True and result.data.schedule.schedule_id == "job"
    assert listed.ok is True and len(listed.data.schedules) == 1
    assert paused.ok is True and paused.data.schedule.state.value == "paused"


def test_scheduler_creation_still_requires_thread(tmp_path) -> None:
    tools = {tool.name: tool for tool in asyncio.run(_catalog(tmp_path).list_tools())}
    token = set_envelope({
        "tenant_id": "tenant", "principal_id": "owner",
    })
    try:
        created = asyncio.run(tools["scheduler_add"].fn(
            agent_id="developer", task="new work", kind="interval",
            interval_seconds=60,
        ))
    finally:
        reset_envelope(token)
    assert not created.ok
    assert created.error == "tool_execution_failed"


def test_scheduler_add_accepts_wire_iso_one_shot_at(tmp_path) -> None:
    """Workflow loop admission sends ``one_shot_at`` as JSON text, not datetime."""
    tools = {tool.name: tool for tool in asyncio.run(_catalog(tmp_path).list_tools())}

    def resolve(target, **kwargs):
        assert target == {"brick_name": "session", "tool_name": "resolve_thread"}
        return {"ok": True, "result": {"structured_content": {"ok": True, "data": {
            "session": {"session_id": "session", "thread_id": "thread"},
        }}}}

    previous = get_service("tool_invoker_for_caller")
    set_service("tool_invoker_for_caller", lambda _caller: resolve)
    token = set_envelope({
        "tenant_id": "tenant", "principal_id": "owner",
        "session_id": "thread", "thread_id": "thread",
    })
    try:
        created = asyncio.run(tools["scheduler_add"].fn(
            agent_id="developer", task="loop cycle", kind="one_shot",
            one_shot_at="2026-09-15T14:35:46.081296Z",
            output_schema="loop-cycle-report-v1", delivery_mode="workflow_loop",
            loop_id="loop", loop_cycle=1, schedule_id="loop_loop_1",
        ))
    finally:
        reset_envelope(token)
        set_service("tool_invoker_for_caller", previous)
    assert created.ok is True, created.error
    schedule = created.data.schedule
    assert schedule.schedule_id == "loop_loop_1"
    assert schedule.one_shot_at.isoformat() == "2026-09-15T14:35:46.081296+00:00"
