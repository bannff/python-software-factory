"""Whole-server strict ingress and exact-envelope regression for Telemetry."""
from __future__ import annotations

import asyncio
from typing import get_type_hints

import pytest

from factory.mcp_utils.interface import ToolResult
from factory.telemetry.server import create_mcp_server
from factory.telemetry.runtime.runtime import TelemetryRuntime

_EXPECTED = {
    "get_capabilities": "deterministic", "health_check": "deterministic",
    "telemetry_get_collection_status": "deterministic",
    "get_metric_registry": "deterministic", "get_exporter_registry": "deterministic",
    "get_metrics_summary": "deterministic", "describe_config_schema": "deterministic",
    "inject_context": "deterministic", "extract_context": "deterministic",
    "flush_telemetry": "operational", "telemetry_run_retention": "operational",
    "record_log": "operational",
    "record_llm_interaction": "operational", "record_agent_execution": "operational",
    "record_tool_invocation": "operational", "start_span": "operational",
    "end_span": "operational", "telemetry_ingest_batch": "operational",
    "telemetry_read_reference": "operational", "telemetry_materialize": "operational",
    "authoring_status": "authoring", "list_configs": "authoring",
    "read_config": "authoring", "write_config": "authoring",
    "write_metric_file": "authoring", "delete_config": "authoring",
    "telemetry_get_views": "deterministic",
}


def _tool(server, name):
    return asyncio.run(server.get_tool(name))


def _tool_names(server) -> set[str]:
    return {tool.name for tool in asyncio.run(server.list_tools())}


def _server(tmp_path) -> object:
    return create_mcp_server(TelemetryRuntime(tmp_path / "telemetry"))


def test_all_tools_are_strict_typed_envelopes(tmp_path) -> None:
    server = _server(tmp_path)
    assert len(_EXPECTED) == 27
    assert _tool_names(server) == set(_EXPECTED)
    for name, category in _EXPECTED.items():
        fn = _tool(server, name).fn
        assert getattr(fn, "_mcp_category") == category
        for attr in ("_mcp_input_model", "_mcp_output_model"):
            model = getattr(fn, attr)
            assert model.model_config["extra"] == "forbid"
            assert model.model_config["strict"] is True
        assert get_type_hints(fn)["return"] == ToolResult[getattr(fn, "_mcp_output_model")]


def test_strict_ingress_defaults_and_normal_negative_outcomes(tmp_path) -> None:
    server = _server(tmp_path)
    with pytest.raises(Exception):
        _tool(server, "flush_telemetry").fn(timeout_ms=1000, unexpected=True)
    flush = _tool(server, "flush_telemetry").fn()
    assert flush.ok and flush.data.ok is False and flush.data.error == "otel_not_initialized"
    health = _tool(server, "health_check").fn()
    assert health.ok and health.data.ok is False and health.data.error == "runtime_not_initialized"
    span = _tool(server, "end_span").fn(span_id="missing")
    assert span.ok and span.data.ok is False and span.data.error == "span_not_found"
    log = _tool(server, "record_log").fn(severity="INFO", body="typed")
    assert log.ok and log.data.recorded == "log"


def test_authoring_modes(tmp_path, monkeypatch) -> None:
    server = _server(tmp_path)
    disabled = _tool(server, "read_config").fn(kind="exporter", item_id="missing")
    assert disabled.ok and disabled.data.error == "authoring_disabled"
    monkeypatch.setenv("TELEMETRY_ENABLE_AUTHORING_TOOLS", "1")
    assert _tool(_server(tmp_path), "authoring_status").fn().data.enabled is True


def test_views_execute_with_typed_dashboard_payload(tmp_path) -> None:
    result = _tool(_server(tmp_path), "telemetry_get_views").fn()
    assert result.ok is True
    assert result.data.views[0]["id"] == "telemetry-dashboard"
