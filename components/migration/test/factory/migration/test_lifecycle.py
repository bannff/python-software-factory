"""Migration start/get lifecycle tests over typed Workflow transport."""
from __future__ import annotations

import asyncio

from factory.mcp_utils.runtime.tool_catalog import ToolCatalog
from factory.migration.mcp.lifecycle import register
from factory.migration.runtime.adapters.receipt_store_sql import SqlReceiptStore
from factory.migration.runtime.lifecycle import project_progress, stable_run_key, start_plan
from factory.migration.runtime.preview import PreviewRuntime
from factory.migration.runtime.receipt_models import (
    ImportOutcome, ImportReceipt, PageCursor, PlanIdentity,
)
from factory.storage.interface import StorageRuntime


def _plan(owner="owner") -> PlanIdentity:
    return PlanIdentity(
        tenant_id="tenant", owner_id=owner, adapter="kirocrew-v1",
        source_fingerprint="a" * 64, plan_digest="sha256:" + "b" * 64,
        kinds=("memory", "lessons"),
    )


def _tool(data):
    return {"ok": True, "result": {"structured_content": {
        "schema_version": "v1", "ok": True, "data": data,
    }}}


def test_start_uses_stable_exact_enrollment_and_replay_key() -> None:
    plan = _plan()
    calls = []

    def invoke(target, **kwargs):
        calls.append((target, kwargs))
        args = kwargs["arguments"]
        return _tool({
            "run_id": "run-1", "run_key": args["run_key"], "status": "running",
            "manifest_digest": args["manifest_digest"], "engine_id": "migration_import",
        })

    first = start_plan(plan, invoke, {"tenant_id": "tenant", "principal_id": "owner"})
    second = start_plan(plan, invoke, {"tenant_id": "tenant", "principal_id": "owner"})
    assert first == second and first.run_id == "run-1"
    assert calls[0][1]["arguments"]["request"]["kinds"] == ["memory", "lessons"]
    assert calls[0][1]["enrollment"] == {
        "run_key": stable_run_key(plan), "manifest_digest": "b" * 64}
    assert calls[0][1]["arguments"]["request"]["page_size"] == 50


def test_get_projects_owner_scoped_receipts_and_cursors(tmp_path) -> None:
    store = SqlReceiptStore(StorageRuntime().get_sql_store(
        "sqlite", db_path=str(tmp_path / "lifecycle.db")))
    plan = _plan()
    store.bind_plan(plan)
    for kind, outcome, record in (
        ("memory", ImportOutcome.IMPORTED, "1" * 64),
        ("memory", ImportOutcome.SKIPPED, "2" * 64),
        ("lessons", ImportOutcome.FAILED, "3" * 64),
    ):
        store.record_receipt(ImportReceipt(
            tenant_id="tenant", owner_id="owner", adapter="kirocrew-v1",
            source_fingerprint="a" * 64, kind=kind, source_record_id=record,
            target_digest="sha256:" + record, outcome=outcome,
        ))
    store.save_cursor(PageCursor(
        tenant_id="tenant", owner_id="owner", adapter="kirocrew-v1",
        source_fingerprint="a" * 64, plan_digest=plan.plan_digest,
        kind="memory", page_index=2,
    ))

    def invoke(_target, **_kwargs):
        return _tool({
            "run_id": "run-1", "workflow_id": "inhouse-execution:migration_import",
            "status": "running", "input": {"engine_id": "migration_import", "request": {
                "tenant_id": "tenant", "owner_id": "owner",
                "source_adapter": "kirocrew-v1", "source_fingerprint": "a" * 64,
                "plan_digest": plan.plan_digest,
                "kinds": ["memory", "lessons"], "page_size": 50,
            }}, "result": None,
        })

    report = project_progress(
        store, invoke, {"tenant_id": "tenant", "principal_id": "owner"}, "run-1")
    memory, lessons = report.progress
    assert (memory.imported, memory.skipped, memory.cursor) == (1, 1, 2)
    assert (lessons.failed, lessons.cursor) == (1, 0)
    assert report.terminal_reason == ""


def test_get_maps_typed_continuation_exhaustion(tmp_path) -> None:
    store = SqlReceiptStore(StorageRuntime().get_sql_store(
        "sqlite", db_path=str(tmp_path / "reason.db")))
    plan = _plan()
    store.bind_plan(plan)

    def invoke(_target, **_kwargs):
        return _tool({
            "run_id": "run-1", "workflow_id": "inhouse-execution:migration_import",
            "status": "failed", "input": {"engine_id": "migration_import", "request": {
                "tenant_id": "tenant", "owner_id": "owner",
                "source_adapter": "kirocrew-v1", "source_fingerprint": "a" * 64,
                "plan_digest": plan.plan_digest,
                "kinds": ["memory", "lessons"], "page_size": 50,
            }}, "result": {"terminal_reason": "continuation_exhausted"},
        })

    report = project_progress(
        store, invoke, {"tenant_id": "tenant", "principal_id": "owner"}, "run-1")
    assert report.terminal_reason == "continuation_exhausted"


def test_public_lifecycle_tools_are_typed_and_authority_bound(tmp_path, monkeypatch) -> None:
    store = SqlReceiptStore(StorageRuntime().get_sql_store(
        "sqlite", db_path=str(tmp_path / "mcp.db")))
    plan = _plan()
    store.bind_plan(plan)
    runtime = PreviewRuntime(None, store)
    catalog = ToolCatalog("migration")
    register(catalog, lambda: runtime)
    tools = {tool.name: tool for tool in asyncio.run(catalog.list_tools())}
    assert tools["migration_start"].fn._mcp_category == "operational"
    assert tools["migration_get"].fn._mcp_category == "deterministic"
    envelope = {"tenant_id": "tenant", "principal_id": "owner"}
    monkeypatch.setattr(
        "factory.migration.mcp.lifecycle.get_envelope", lambda: envelope,
    )
    monkeypatch.setattr(
        "factory.migration.mcp.operational.get_envelope", lambda: envelope,
    )

    def invoke(target, **kwargs):
        args = kwargs["arguments"]
        if target["tool_name"] == "enroll_execution":
            return _tool({
                "run_id": "run-1", "run_key": args["run_key"],
                "status": "running", "manifest_digest": args["manifest_digest"],
                "engine_id": "migration_import",
            })
        return _tool({
            "run_id": "run-1", "workflow_id": "inhouse-execution:migration_import",
            "status": "running", "input": {"engine_id": "migration_import", "request": args.get("request", {
                "tenant_id": "tenant", "owner_id": "owner",
                "source_adapter": "kirocrew-v1", "source_fingerprint": "a" * 64,
                "plan_digest": plan.plan_digest,
                "kinds": ["memory", "lessons"], "page_size": 50,
            })}, "result": None,
        })

    monkeypatch.setattr(
        "factory.migration.mcp.lifecycle.get_service",
        lambda name: (lambda caller: invoke)
        if name == "tool_invoker_for_caller" else None,
    )
    started = tools["migration_start"].fn(
        plan_digest=plan.plan_digest, kinds=["memory", "lessons"])
    assert started.ok and started.data.run_id == "run-1"
    report = tools["migration_get"].fn(run_id="run-1")
    assert report.ok and len(report.data.progress) == 2


def test_public_start_rejects_foreign_or_mismatched_plan(tmp_path, monkeypatch) -> None:
    store = SqlReceiptStore(StorageRuntime().get_sql_store(
        "sqlite", db_path=str(tmp_path / "foreign.db")))
    store.bind_plan(_plan("owner"))
    runtime = PreviewRuntime(None, store)
    catalog = ToolCatalog("migration")
    register(catalog, lambda: runtime)
    tool = asyncio.run(catalog.get_tool("migration_start"))
    envelope = {"tenant_id": "tenant", "principal_id": "other"}
    monkeypatch.setattr(
        "factory.migration.mcp.lifecycle.get_envelope", lambda: envelope,
    )
    monkeypatch.setattr(
        "factory.migration.mcp.operational.get_envelope", lambda: envelope,
    )
    result = tool.fn(plan_digest=_plan().plan_digest, kinds=["memory", "lessons"])
    assert result.ok is False and result.error == "migration_lifecycle_unavailable"
