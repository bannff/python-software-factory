"""Typed MCP contract tests for read-only operational migration preview."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from factory.mcp_utils.interface import ToolCatalog
from factory.migration.mcp.contracts import PreviewInput, PreviewOutput
from factory.migration.mcp.operational import _ERROR, register
from factory.migration.runtime.adapters.receipt_store_sql import SqlReceiptStore
from factory.migration.runtime.preview import PreviewRuntime
from factory.storage.interface import get_sql_store
from factory.storage.runtime.runtime import reset_runtime


async def _tool(runtime: PreviewRuntime):
    catalog = ToolCatalog("test")
    register(catalog, lambda: runtime)
    tools = {tool.name: tool for tool in await catalog.list_tools()}
    return tools["migration_preview"]


def _runtime(tmp_path: Path) -> PreviewRuntime:
    reset_runtime()
    root = tmp_path / "crew"
    root.mkdir()
    (root / "lessons.jsonl").write_text(json.dumps({"rule": "Keep evidence"}) + "\n")
    return PreviewRuntime(root, SqlReceiptStore(get_sql_store(
        "sqlite", db_path=str(tmp_path / "migration.db"))))


@pytest.mark.asyncio
async def test_preview_tool_is_operational_and_typed(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        "factory.migration.mcp.operational.get_envelope",
        lambda: {"tenant_id": "tenant", "principal_id": "owner"},
    )
    tool = await _tool(_runtime(tmp_path))
    assert tool.fn._mcp_category == "operational"
    result = tool.fn(kinds=["lessons"])
    assert result.ok is True and isinstance(result.data, PreviewOutput)
    assert result.data.reports[0].eligible == 1
    assert set(result.data.model_dump()) == {
        "source", "source_fingerprint", "plan_digest", "status", "files",
        "reports", "samples", "snapshot_diagnostics",
    }


@pytest.mark.asyncio
async def test_missing_identity_maps_to_fixed_safe_error(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("factory.migration.mcp.operational.get_envelope", lambda: None)
    result = (await _tool(_runtime(tmp_path))).fn(kinds=["lessons"])
    assert result.ok is False and result.error == _ERROR
    assert "crew" not in json.dumps(result.model_dump())


def test_preview_ingress_is_strict_and_unique() -> None:
    with pytest.raises(ValidationError):
        PreviewInput(kinds=["lessons"], unexpected=True)
    with pytest.raises(ValidationError):
        PreviewInput(kinds=["lessons", "lessons"])
    with pytest.raises(ValidationError):
        PreviewInput(source="other")


@pytest.mark.asyncio
async def test_receipt_failure_maps_to_fixed_safe_error(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        "factory.migration.mcp.operational.get_envelope",
        lambda: {"tenant_id": "tenant", "principal_id": "owner"},
    )
    runtime = _runtime(tmp_path)

    def fail_receipt(_plan):
        raise RuntimeError("SENTINEL storage detail")

    monkeypatch.setattr(runtime.receipts, "bind_plan", fail_receipt)
    result = (await _tool(runtime)).fn(kinds=["lessons"])
    assert result.ok is False and result.error == _ERROR
    assert "SENTINEL" not in json.dumps(result.model_dump())
