"""Tests for the typed Worker authoring MCP tools."""
from __future__ import annotations

import asyncio

import pytest

from factory.mcp_utils.interface import ToolResult
from factory.worker.runtime.runtime import WorkerRuntime, reset_runtime
from factory.worker.server import create_mcp_server


@pytest.fixture()
def mcp_server():
    reset_runtime()
    runtime = WorkerRuntime()
    server = create_mcp_server(runtime, enable_authoring=True)
    yield server
    reset_runtime()


@pytest.fixture()
def mcp_server_no_authoring():
    reset_runtime()
    runtime = WorkerRuntime()
    server = create_mcp_server(runtime, enable_authoring=False)
    yield server
    reset_runtime()


def _get_tool(server, name: str):
    return asyncio.run(server.get_tool(name))


def test_status_is_typed_and_reports_catalog(mcp_server) -> None:
    result = _get_tool(mcp_server, "worker.authoring.get_status").fn()
    assert isinstance(result, ToolResult)
    assert result.ok and result.data.enabled is True
    assert result.data.available_backends == ["celery", "dagster", "fargate_sqs"]
    assert result.data.current_backend == "celery"


def test_disabled_authoring_is_discoverable_and_typed(mcp_server_no_authoring) -> None:
    result = _get_tool(mcp_server_no_authoring, "worker.authoring.switch_backend").fn(
        backend="dagster",
    )
    assert result.ok and result.data.switched is False
    assert result.data.error == "authoring_disabled"


def test_switch_backend_uses_runtime_public_method(mcp_server) -> None:
    tool = _get_tool(mcp_server, "worker.authoring.switch_backend")
    result = tool.fn(backend="dagster")
    assert result.ok and result.data.switched is True
    assert result.data.backend == "dagster"
    assert _get_tool(mcp_server, "worker.authoring.get_status").fn().data.current_backend == "dagster"


def test_unknown_backend_is_typed_negative_result(mcp_server) -> None:
    result = _get_tool(mcp_server, "worker.authoring.switch_backend").fn(backend="unknown")
    assert result.ok and result.data.switched is False
    assert result.data.backend is None
    assert result.data.error == "unknown_backend"


def test_config_applies_queues_and_reports_unsupported_concurrency(mcp_server) -> None:
    result = _get_tool(mcp_server, "worker.authoring.set_config").fn(
        queues=["high", "low"], concurrency=4,
    )
    assert result.ok and result.data.updated is True
    assert result.data.changes == {"queues": ["high", "low"]}
    assert result.data.unsupported == ["concurrency"]
    assert result.data.error is None


def test_concurrency_only_is_not_echoed_as_an_update(mcp_server) -> None:
    result = _get_tool(mcp_server, "worker.authoring.set_config").fn(concurrency=4)
    assert result.ok and result.data.updated is False
    assert result.data.changes == {}
    assert result.data.unsupported == ["concurrency"]
    assert result.data.error == "unsupported_configuration"
