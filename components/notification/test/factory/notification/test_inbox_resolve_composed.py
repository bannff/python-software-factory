"""Composed deep-link resolution over the real native dispatch rail.

Wires ``NativeEnvelopeInvoker`` as ``tool_invoker_for_caller`` and drives the
Notification resolver end-to-end into real source bricks:

* canvas   — global-allowlist authorization via the new ``ui_resolve_canvas``;
* schedule — owner-scoped ``scheduler_get`` (foreign owner is opaque);
* workflow — ``workflow.get_run`` same-tenant foreign-owner is opaque, proving
  the initiating-principal parity hardening through the rail.

Every deviation collapses to the single fixed ``notification_target_not_found``.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path

import pytest
import yaml

from factory.mcp_server.runtime.aggregator import MCPAggregator
from factory.mcp_server.runtime.native_invoker import NativeEnvelopeInvoker
from factory.mcp_utils.interface import (
    ToolCatalog, reset_envelope, set_envelope, set_service,
)
from factory.notification.runtime.dispatcher import NotificationRuntime
from factory.notification.runtime.inbox_models import NotificationRecord, Priority
from factory.notification.runtime.inbox_targets import (
    CanvasTarget, ScheduleTarget, WorkflowRunTarget,
)
from factory.notification.server import create_mcp_server as notification_server

_T, _A, _B = "tenant", "owner-a", "owner-b"
_NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _rec(runtime, nid, target, owner=_A):
    runtime.inbox_store.create_or_replay(NotificationRecord(
        tenant_id=_T, owner_id=owner, notification_id=nid, kind="k", title="t",
        priority=Priority.DEFAULT, target=target, dedupe_key=nid, created_at=_NOW))


def _aggregator(runtime, extra: dict[str, object]) -> MCPAggregator:
    aggregator = MCPAggregator(ToolCatalog("root"))
    aggregator.set_available_bricks(["notification", *extra])
    aggregator._lazy._cache["notification"] = notification_server(runtime)
    for name, catalog in extra.items():
        aggregator._lazy._cache[name] = catalog
    return aggregator


def _resolve(runtime, aggregator, nid, envelope):
    set_service("tool_invoker_for_caller", NativeEnvelopeInvoker(aggregator).for_caller)
    tool = asyncio.run(notification_server(runtime).get_tool("inbox_resolve_target"))
    token = set_envelope(envelope)
    try:
        return tool.fn(notification_id=nid)
    finally:
        reset_envelope(token)


def test_canvas_authorized_and_unknown_is_opaque(tmp_path) -> None:
    from factory.ui.server import create_mcp_server as ui_server
    runtime = NotificationRuntime(tmp_path)
    _rec(runtime, "good", CanvasTarget(view_id="welcome"))
    _rec(runtime, "bogus", CanvasTarget(view_id="nope"))
    aggregator = _aggregator(runtime, {"ui": ui_server()})
    env = {"tenant_id": _T, "principal_id": _A}
    good = _resolve(runtime, aggregator, "good", env)
    bogus = _resolve(runtime, aggregator, "bogus", env)
    assert good.ok is True and good.data.target.view_id == "welcome"
    assert bogus.ok is False and bogus.error == "notification_target_not_found"


def test_schedule_owner_scoped(tmp_path) -> None:
    from factory.scheduler.runtime.adapters.sql import SQLScheduleStore
    from factory.scheduler.runtime.lifecycle import SchedulerLifecycle
    from factory.scheduler.runtime.runtime import SchedulerRuntime
    from factory.scheduler.server import create_mcp_server as scheduler_server
    from factory.storage.interface import get_sql_store

    lifecycle = SchedulerLifecycle(
        SQLScheduleStore(get_sql_store("sqlite", db_path=str(tmp_path / "s.db"))))
    schedule = lifecycle.create(_T, _A, "sess", "thread", "agent", "task",
                                "interval", interval_seconds=60)
    runtime = NotificationRuntime(tmp_path)
    _rec(runtime, "own", ScheduleTarget(schedule_id=schedule.schedule_id))
    _rec(runtime, "foreign", ScheduleTarget(schedule_id=schedule.schedule_id), owner=_B)
    aggregator = _aggregator(runtime, {"scheduler": scheduler_server(SchedulerRuntime(lifecycle))})
    own = _resolve(runtime, aggregator, "own",
                   {"tenant_id": _T, "principal_id": _A, "session_id": "thread"})
    foreign = _resolve(runtime, aggregator, "foreign",
                       {"tenant_id": _T, "principal_id": _B, "session_id": "thread"})
    assert own.ok is True and own.data.target.schedule_id == schedule.schedule_id
    assert foreign.ok is False and foreign.error == "notification_target_not_found"


def _workflow_runtime(tmp_path: Path):
    from factory.workflow.runtime.runtime import WorkflowRuntime
    cfg = tmp_path / "wf"
    (cfg / "workflows").mkdir(parents=True)
    (cfg / "settings.yaml").write_text(yaml.safe_dump({
        "service": {"name": "workflow-module"},
        "storage": {"backend": "sqlite", "sqlite": {"filename": "state.sqlite"}},
        "authoring": {"enabled": False}}))
    (cfg / "workflows" / "ex.yaml").write_text(yaml.safe_dump({
        "schema_version": "v1", "id": "ex", "name": "Ex", "version": 1,
        "steps": [{"id": "start", "kind": "noop"}]}))
    return WorkflowRuntime.from_config_dir(cfg)


def test_workflow_same_tenant_foreign_owner_is_opaque(tmp_path) -> None:
    from factory.workflow.runtime.envelope import parse_envelope
    from factory.workflow.server import create_mcp_server as workflow_server

    wf = _workflow_runtime(tmp_path)
    wf.start_run(workflow_name_or_id="ex", input={},
                 envelope=parse_envelope({"run_id": "wf-1", "tenant_id": _T,
                                          "principal_id": _A}))
    runtime = NotificationRuntime(tmp_path)
    _rec(runtime, "own", WorkflowRunTarget(run_id="wf-1"))
    _rec(runtime, "foreign", WorkflowRunTarget(run_id="wf-1"), owner=_B)
    aggregator = _aggregator(runtime, {"workflow": workflow_server(wf)})
    own = _resolve(runtime, aggregator, "own", {"tenant_id": _T, "principal_id": _A})
    foreign = _resolve(runtime, aggregator, "foreign", {"tenant_id": _T, "principal_id": _B})
    assert own.ok is True and own.data.target.run_id == "wf-1"
    assert foreign.ok is False and foreign.error == "notification_target_not_found"
