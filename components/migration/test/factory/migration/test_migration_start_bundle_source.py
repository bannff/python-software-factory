"""migration_start now accepts source="companion-x-v1" to start a
bundle-bound plan — the last missing link connecting BundlePreviewRuntime's
bound plans to the existing lifecycle/apply engine. Row 54 Portability."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from factory.mcp_utils.interface import ToolCatalog, get_service, set_service
from factory.migration.mcp import lifecycle
from factory.migration.runtime.adapters.receipt_store_sql import SqlReceiptStore
from factory.migration.runtime.bundle_preview import BundlePreviewRuntime
from factory.migration.runtime.preview import PreviewRuntime


def _digest(payload) -> str:
    return f"sha256:{hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()}"


def _write_bundle(path: Path) -> None:
    records = [{"identity": "m1", "content": "hello from a bundle", "kind": "semantic", "tags": []}]
    kinds = {"memory": {"records": records, "digest": _digest(records)}}
    bundle = {
        "bundle_version": 1, "adapter": "companion-x-v1",
        "producer": {"app": "companion-x", "kinds": ["memory"]},
        "content_digest": _digest(kinds), "kinds": kinds,
    }
    path.write_text(json.dumps(bundle))


async def _start_tool(kirocrew_runtime: PreviewRuntime):
    catalog = ToolCatalog("test")
    lifecycle.register(catalog, lambda: kirocrew_runtime)
    tools = {tool.name: tool for tool in await catalog.list_tools()}
    return tools["migration_start"]


@pytest.mark.asyncio
async def test_migration_start_accepts_a_bundle_bound_plan(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(
        "factory.migration.mcp.operational.get_envelope",
        lambda: {"tenant_id": "tenant-a", "principal_id": "owner-a"},
    )
    monkeypatch.setattr(
        "factory.migration.mcp.lifecycle.get_envelope",
        lambda: {"tenant_id": "tenant-a", "principal_id": "owner-a"},
    )
    db_path = str(tmp_path / "migration.db")
    _write_bundle(tmp_path / "backup.cxbundle.json")

    def resolver(bundle_ref: str) -> Path:
        return tmp_path / bundle_ref

    bundle_runtime = BundlePreviewRuntime(resolver, SqlReceiptStore(db_path=db_path))
    preview = bundle_runtime.preview("tenant-a", "owner-a", "backup.cxbundle.json", None)

    calls: list[dict] = []

    def invoker_factory(caller: str):
        def invoke(target, *, arguments, idempotency_key, envelope, enrollment=None, migration_import=None):
            calls.append({"target": target})
            return {"ok": True, "result": {"structured_content": {
                "schema_version": "v1", "ok": True,
                "data": {
                    "run_id": "run-1", "status": "pending",
                    "run_key": enrollment["run_key"] if enrollment else "",
                    "manifest_digest": enrollment["manifest_digest"] if enrollment else "",
                    "engine_id": "migration_import",
                },
            }}}
        return invoke

    previous = get_service("tool_invoker_for_caller")
    set_service("tool_invoker_for_caller", invoker_factory)
    try:
        kirocrew_runtime = PreviewRuntime(None, SqlReceiptStore(db_path=db_path))
        tool = await _start_tool(kirocrew_runtime)
        result = tool.fn(plan_digest=preview.plan.plan_digest, kinds=["memory"], source="companion-x-v1")
    finally:
        set_service("tool_invoker_for_caller", previous)

    assert result.ok is True
    assert result.data.run_id
    assert calls  # at least one target call was made through the real workflow-run seam


@pytest.mark.asyncio
async def test_migration_start_still_defaults_to_kirocrew_v1(tmp_path: Path, monkeypatch):
    """Backward-compat guard: the new source parameter's default must not
    change existing kirocrew-v1 behavior for callers who omit it."""
    monkeypatch.setattr(
        "factory.migration.mcp.operational.get_envelope",
        lambda: {"tenant_id": "tenant-a", "principal_id": "owner-a"},
    )
    monkeypatch.setattr(
        "factory.migration.mcp.lifecycle.get_envelope",
        lambda: {"tenant_id": "tenant-a", "principal_id": "owner-a"},
    )
    root = tmp_path / "crew"
    root.mkdir()
    (root / "lessons.jsonl").write_text(json.dumps({"rule": "Keep evidence"}) + "\n")
    from factory.migration.runtime.source_models import SourceKind
    runtime = PreviewRuntime(root, SqlReceiptStore(db_path=str(tmp_path / "migration.db")))
    preview = runtime.preview("tenant-a", "owner-a", (SourceKind.LESSONS,))

    previous = get_service("tool_invoker_for_caller")

    def invoker_factory(caller: str):
        def invoke(target, *, arguments, idempotency_key, envelope, enrollment=None, migration_import=None):
            return {"ok": True, "result": {"structured_content": {
                "schema_version": "v1", "ok": True,
                "data": {
                    "run_id": "run-1", "status": "pending",
                    "run_key": enrollment["run_key"] if enrollment else "",
                    "manifest_digest": enrollment["manifest_digest"] if enrollment else "",
                    "engine_id": "migration_import",
                },
            }}}
        return invoke

    set_service("tool_invoker_for_caller", invoker_factory)
    try:
        tool = await _start_tool(runtime)
        result = tool.fn(plan_digest=preview.plan.plan_digest, kinds=["lessons"])  # source omitted
    finally:
        set_service("tool_invoker_for_caller", previous)

    assert result.ok is True
    assert result.data.run_id
