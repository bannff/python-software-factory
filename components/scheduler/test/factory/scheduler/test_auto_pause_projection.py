"""Composed Scheduler -> protected Notification auto-pause projection.

Wires the real ``NativeEnvelopeInvoker`` as the caller-bound tool invoker and
drives Scheduler ``project_outcome`` end-to-end into the real Notification
``inbox_publish`` service-only tool, proving the durable record is persisted
through the caller-binding rail (events brick is absent, so that best-effort
projection is swallowed — Scheduler truth is never gated on it).
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from factory.mcp_server.runtime.aggregator import MCPAggregator
from factory.mcp_server.runtime.native_invoker import NativeEnvelopeInvoker
from factory.mcp_utils.interface import get_service, set_service
from factory.mcp_utils.runtime.tool_catalog import ToolCatalog
from factory.notification.runtime.dispatcher import NotificationRuntime
from factory.notification.server import create_mcp_server
from factory.scheduler.runtime.observability import project_outcome

_T, _OWNER, _SID = "tenant", "owner", "nightly"


def _schedule():
    return SimpleNamespace(tenant_id=_T, owner_id=_OWNER, schedule_id=_SID,
                           origin_thread_id="thread")


def _fire():
    return SimpleNamespace(fire_sequence=5, launch_id="sched_nightly_5",
                           workflow_run_id="run-5")


@pytest.mark.asyncio
async def test_scheduler_auto_pause_persists_through_protected_notification(tmp_path) -> None:
    runtime = NotificationRuntime(tmp_path)
    aggregator = MCPAggregator(ToolCatalog("root"))
    aggregator.set_available_bricks(["notification"])
    aggregator._lazy._cache["notification"] = create_mcp_server(runtime)
    native = NativeEnvelopeInvoker(aggregator)
    previous = get_service("tool_invoker_for_caller")
    set_service("tool_invoker_for_caller", native.for_caller)
    try:
        await project_outcome(_schedule(), _fire(), "failed", True)
    finally:
        set_service("tool_invoker_for_caller", previous)
    records = runtime.inbox_list(_T, _OWNER, limit=10)
    assert len(records) == 1
    record = records[0]
    assert record.dedupe_key == "scheduler-auto-pause:nightly:5"
    assert record.title == "Schedule auto-paused"


@pytest.mark.asyncio
async def test_scheduler_truth_survives_when_invoker_absent(tmp_path) -> None:
    runtime = NotificationRuntime(tmp_path)
    set_service("tool_invoker_for_caller", None)
    # Best-effort projection cannot raise into the scheduler outcome path.
    await project_outcome(_schedule(), _fire(), "failed", True)
    assert runtime.inbox_list(_T, _OWNER, limit=10) == []
