"""Strict public MCP contract tests for Logger."""
from __future__ import annotations

import asyncio
from typing import get_type_hints

import pytest
from mcp.shared.exceptions import MCPError

from factory.logger.runtime.adapters.structlog_sink import StructlogSink
from factory.logger.runtime.runtime import LoggerRuntime
from factory.logger.server import create_mcp_server
from factory.mcp_utils.interface import ToolResult

_NAMES = {
    "logger.get_capabilities": "deterministic",
    "logger.health_check": "deterministic",
    "logger.describe_config_schema": "deterministic",
    "logger.tail": "deterministic",
    "logger.search": "deterministic",
    "logger.info": "operational",
    "logger.error": "operational",
    "logger.warning": "operational",
    "logger.debug": "operational",
    "logger.clear": "authoring",
}


@pytest.fixture
def runtime(tmp_path) -> LoggerRuntime:
    """Create an isolated file-backed Logger runtime."""
    return LoggerRuntime(log_dir=tmp_path)


@pytest.fixture
def mcp(runtime):
    """Create a fresh Logger MCP server for every contract test."""
    return create_mcp_server(runtime)


def _tool(mcp, name: str):
    return asyncio.run(mcp.get_tool(name))


def _run(tool, arguments: dict):
    return asyncio.run(tool.run(arguments))


def test_fresh_server_has_exact_dotted_catalog_and_categories(mcp) -> None:
    tools = asyncio.run(mcp.list_tools())
    assert {tool.name for tool in tools} == set(_NAMES)
    assert {tool.name: getattr(tool.fn, "_mcp_category") for tool in tools} == _NAMES


def test_every_tool_has_strict_local_dtos_and_exact_typed_return(mcp) -> None:
    for name in _NAMES:
        tool = _tool(mcp, name)
        input_model = getattr(tool.fn, "_mcp_input_model")
        output_model = getattr(tool.fn, "_mcp_output_model")
        assert input_model.__module__ == "factory.logger.mcp.contracts"
        assert output_model.__module__ == "factory.logger.mcp.contracts"
        assert input_model.model_config["extra"] == "forbid"
        assert input_model.model_config["strict"] is True
        assert get_type_hints(tool.fn)["return"] == ToolResult[output_model]


def test_contract_tools_and_defaults(mcp) -> None:
    capabilities = _tool(mcp, "logger.get_capabilities").fn()
    health = _tool(mcp, "logger.health_check").fn()
    schema = _tool(mcp, "logger.describe_config_schema").fn()
    tail = _tool(mcp, "logger.tail").fn()
    search = _tool(mcp, "logger.search").fn()
    assert capabilities.data.document["name"] == "logger"
    assert health.data.status in {"healthy", "degraded"}
    assert health.data.sink.backend == "file"
    assert "log_file" not in health.data.model_dump()
    assert schema.data.document["type"] == "object"
    assert tail.data.count == 0
    assert search.data.count == 0


def test_all_log_tools_tail_search_and_clear_redaction(mcp) -> None:
    for name, level in (
        ("logger.info", "info"), ("logger.error", "error"),
        ("logger.warning", "warning"), ("logger.debug", "debug"),
    ):
        result = _tool(mcp, name).fn(
            message=f"{level} message", source="test", context={"level": level},
        )
        assert result.ok and result.data.level == level
    tail = _tool(mcp, "logger.tail").fn(lines=4)
    search = _tool(mcp, "logger.search").fn(level="warning", limit=1)
    clear = _tool(mcp, "logger.clear").fn()
    assert tail.data.count == 4
    assert search.data.records[0].level == "warning"
    assert clear.data.model_dump() == {"status": "cleared"}


@pytest.mark.parametrize("name,arguments", [
    ("logger.tail", {"lines": "1"}),
    ("logger.tail", {"lines": 0}),
    ("logger.search", {"level": "trace"}),
    ("logger.search", {"limit": 0}),
    ("logger.info", {"message": "ok", "context": {"bad": object()}}),
    ("logger.info", {"message": "ok", "unexpected": True}),
])
def test_raw_invalid_payloads_fail_at_the_mcp_boundary(mcp, name, arguments) -> None:
    with pytest.raises(MCPError, match="Invalid arguments"):
        _run(_tool(mcp, name), arguments)


def test_unexpected_runtime_failures_are_safe_typed_envelopes(mcp, runtime, monkeypatch) -> None:
    monkeypatch.setattr(
        runtime, "info", lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("/secret/log")),
    )
    result = _tool(mcp, "logger.info").fn(message="safe")
    assert result == ToolResult(ok=False, error="logger_operation_failed")


def test_resources_and_prompts_are_retained(mcp) -> None:
    resources = asyncio.run(mcp.list_resources())
    prompts = asyncio.run(mcp.list_prompts())
    assert resources
    assert prompts


def test_query_outputs_redact_persisted_paths_and_exception_detail(mcp) -> None:
    _tool(mcp, "logger.info").fn(
        message="failed /private/secret.txt",
        source="/private/source-token",
        run_id="/private/run-token",
        context={
            "error": "Traceback: /private/secret.txt",
            "Exception": "sensitive exception detail",
            "exception_detail": "sensitive exception detail",
            "nested": {"path": "/private/nested.txt"},
        },
    )
    for result in (
        _tool(mcp, "logger.tail").fn(lines=1),
        _tool(mcp, "logger.search").fn(level="info", limit=1),
    ):
        payload = result.data.model_dump_json()
        assert "/private/" not in payload
        assert "Traceback" not in payload
        assert "sensitive exception detail" not in payload
        assert "[redacted]" in payload


def test_health_supports_non_file_sink_without_leaking_adapter_details(tmp_path) -> None:
    mcp = create_mcp_server(LoggerRuntime(log_dir=tmp_path, sink=StructlogSink()))
    result = _tool(mcp, "logger.health_check").fn()
    assert result.ok
    assert result.data.status == "healthy"
    assert result.data.sink.model_dump() == {
        "backend": "structlog", "writable": True, "log_size": None, "exists": None,
    }
