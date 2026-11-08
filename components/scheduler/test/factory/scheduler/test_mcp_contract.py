from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

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
    assert created.error == "scheduler_identity_required", "must be typed, not tool_execution_failed"


def test_scheduler_add_accepts_wire_iso_one_shot_at(tmp_path) -> None:
    """Workflow loop admission sends ``one_shot_at`` as JSON text, not datetime."""
    tools = {tool.name: tool for tool in asyncio.run(_catalog(tmp_path).list_tools())}

    def resolve(target, **kwargs):
        if target["tool_name"] == "get_agent_registry":
            data = {"count": 1, "agents": [{"id": "developer"}]}
        else:
            assert target == {"brick_name": "session", "tool_name": "ensure_thread"}
            data = {"session": {"session_id": "session", "thread_id": "thread"}}
        return {"ok": True, "result": {"structured_content": {"ok": True, "data": data}}}

    wire = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat().replace("+00:00", "Z")
    previous = get_service("tool_invoker_for_caller")
    set_service("tool_invoker_for_caller", lambda _caller: resolve)
    token = set_envelope({
        "tenant_id": "tenant", "principal_id": "owner",
        "session_id": "thread", "thread_id": "thread",
    })
    try:
        created = asyncio.run(tools["scheduler_add"].fn(
            agent_id="developer", task="loop cycle", kind="one_shot",
            one_shot_at=wire,
            output_schema="loop-cycle-report-v1", delivery_mode="workflow_loop",
            loop_id="loop", loop_cycle=1, schedule_id="loop_loop_1",
        ))
    finally:
        reset_envelope(token)
        set_service("tool_invoker_for_caller", previous)
    assert created.ok is True, created.error
    schedule = created.data.schedule
    assert schedule.schedule_id == "loop_loop_1"
    assert schedule.one_shot_at.isoformat() == wire.replace("Z", "+00:00")


def test_scheduler_add_reports_a_typed_error_when_the_origin_session_is_missing(tmp_path) -> None:
    tools = {tool.name: tool for tool in asyncio.run(_catalog(tmp_path).list_tools())}

    def resolve(_target, **_kwargs):
        return {"ok": True, "result": {"structured_content": {"ok": False, "error": "session_not_found"}}}

    previous = get_service("tool_invoker_for_caller")
    set_service("tool_invoker_for_caller", lambda _caller: resolve)
    token = set_envelope({"tenant_id": "tenant", "principal_id": "owner", "thread_id": "ghost"})
    try:
        created = asyncio.run(tools["scheduler_add"].fn(
            agent_id="developer", task="work", kind="interval", interval_seconds=60,
        ))
    finally:
        reset_envelope(token)
        set_service("tool_invoker_for_caller", previous)
    assert not created.ok and created.error == "scheduler_origin_not_found"


def test_scheduler_trigger_types_stale_revision_and_missing_schedule(tmp_path) -> None:
    tools = {tool.name: tool for tool in asyncio.run(_catalog(tmp_path).list_tools())}
    token = set_envelope({"tenant_id": "tenant", "principal_id": "owner"})
    try:
        stale = asyncio.run(tools["scheduler_trigger"].fn(schedule_id="job", expected_revision=99))
        missing = asyncio.run(tools["scheduler_trigger"].fn(schedule_id="nope", expected_revision=1))
    finally:
        reset_envelope(token)
    assert stale.error == "schedule_revision_conflict"
    assert missing.error == "schedule_not_found"


def test_scheduler_add_on_a_cold_thread_ensures_the_origin_session(tmp_path, monkeypatch) -> None:
    """A thread that never spoke has no Session row yet (#223); creating a
    schedule must register it, with the same default model chat uses."""
    monkeypatch.setenv("COMPANION_X_CHAT_MODEL", "m-test")
    tools = {tool.name: tool for tool in asyncio.run(_catalog(tmp_path).list_tools())}
    calls: list[tuple[dict, dict]] = []

    def invoke(target, **kwargs):
        calls.append((target, kwargs["arguments"]))
        if target["tool_name"] == "get_agent_registry":
            data = {"count": 1, "agents": [{"id": "developer"}]}
        else:
            data = {"session": {"session_id": "s-new", "thread_id": "cold"}}
        return {"ok": True, "result": {"structured_content": {"ok": True, "data": data}}}

    previous = get_service("tool_invoker_for_caller")
    set_service("tool_invoker_for_caller", lambda _caller: invoke)
    token = set_envelope({"tenant_id": "tenant", "principal_id": "owner", "thread_id": "cold"})
    try:
        created = asyncio.run(tools["scheduler_add"].fn(
            agent_id="developer", task="nightly report\nmore", kind="interval",
            interval_seconds=3600,
        ))
    finally:
        reset_envelope(token)
        set_service("tool_invoker_for_caller", previous)
    assert created.ok is True, created.error
    assert created.data.schedule.origin_session_id == "s-new"
    (target, args), = [c for c in calls if c[0]["tool_name"] == "ensure_thread"]
    assert target["brick_name"] == "session"
    assert args["thread_id"] == "cold" and args["agent_id"] == "developer"
    assert args["model"] == "m-test" and args["title"] == "nightly report"
