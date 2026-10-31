"""MCP registration and flat schema contracts for the CAN terminal."""
from __future__ import annotations

import asyncio
from pathlib import Path

from factory.mcp_utils.runtime.tool_catalog import ToolCatalog
import pytest

from factory.dataset.mcp import can_terminal
from factory.dataset.server import create_mcp_server


def _tool(mcp: ToolCatalog, name: str):
    return asyncio.run(mcp.get_tool(name))


def test_terminal_is_registered_with_required_attempt_and_dataset_inputs(
    tmp_path: Path,
) -> None:
    tool = _tool(create_mcp_server(tmp_path), "dataset_materialize_can_training_bundle")
    schema = tool.fn._mcp_input_model.model_json_schema(mode="validation")
    assert {"attempt_id", "mf4_dir"}.issubset(schema["required"])
    assert "dbc_path" not in schema["required"]
    assert {
        "vehicle_id", "storage_root", "max_samples", "config_overrides",
        "use_context", "context_sources", "emit_timespans",
        "dbc_catalog_id", "dbc_catalog_version", "vehicle_alias",
        "vehicle_make", "vehicle_model", "vehicle_year",
        "message_fingerprints", "failure_pattern_refs",
    }.issubset(schema["properties"])


def test_terminal_mcp_delegates_flat_request_and_storage_root(
    tmp_path: Path, monkeypatch,
) -> None:
    seen = {}

    def materialize(request, root):
        seen.update({"request": request, "root": root})
        return {
            "schema_version": "1.0", "status": "completed", "attempt_id": request.attempt_id,
            "request_sha256": "a" * 64, "vehicle_id": request.vehicle_id,
            "artifacts": {}, "training_bundle": {"prepared_by_can_id": {}},
        }

    monkeypatch.setattr(can_terminal, "dataset_materialize_can_training_bundle", materialize)
    mcp = ToolCatalog("dataset-terminal")
    can_terminal.register(mcp, tmp_path / "registered")
    result = _tool(mcp, "dataset_materialize_can_training_bundle").fn({
        "attempt_id": "attempt-1", "mf4_dir": "/captures", "dbc_path": "/vehicle.dbc",
        "storage_root": str(tmp_path / "registered" / "override"), "use_context": True,
        "context_sources": ["/weather.json"],
    }).data
    assert result.status == "completed"
    assert seen["root"] == (tmp_path / "registered" / "override").resolve()
    assert seen["request"].attempt_id == "attempt-1"
    assert seen["request"].context_sources == ("/weather.json",)


def test_terminal_mcp_rejects_storage_root_outside_registered_root(
    tmp_path: Path,
) -> None:
    mcp = ToolCatalog("dataset-terminal")
    can_terminal.register(mcp, tmp_path / "registered")
    result = _tool(mcp, "dataset_materialize_can_training_bundle").fn({
        "attempt_id": "attempt-1", "mf4_dir": "/captures", "dbc_path": "/vehicle.dbc",
        "storage_root": str(tmp_path / "outside"),
    })
    assert result.ok is False
    assert result.data is None
    assert result.error == "tool_execution_failed"
