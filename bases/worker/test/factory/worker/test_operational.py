"""Tests for typed Worker operational MCP tools."""
from __future__ import annotations

import asyncio

import pytest

from factory.mcp_utils.interface import ToolResult
from factory.worker.runtime.runtime import WorkerRuntime, reset_runtime
from factory.worker.server import create_mcp_server


@pytest.fixture()
def mcp_server():
    reset_runtime()
    server = create_mcp_server(WorkerRuntime())
    yield server
    reset_runtime()


def _get_tool(server, name: str):
    return asyncio.run(server.get_tool(name))


def test_send_task_returns_typed_negative_without_a_broker(mcp_server) -> None:
    result = _get_tool(mcp_server, "worker.send_task").fn(name="factory.execute_tool")
    assert isinstance(result, ToolResult)
    assert result.ok and result.data.task == "factory.execute_tool"
    assert result.data.dispatched is False
    assert result.data.error == "worker_dispatch_failed"


def test_execute_tool_is_policy_bounded(mcp_server) -> None:
    result = _get_tool(mcp_server, "worker.execute_tool").fn(tool_name="nonexistent_tool")
    assert result.ok and result.data.tool == "nonexistent_tool"
    assert result.data.error == "bridge_access_denied"
    assert "secret" not in result.model_dump_json()


def test_list_mcp_tools_is_typed_and_default_deny(mcp_server) -> None:
    result = _get_tool(mcp_server, "worker.list_mcp_tools").fn()
    assert isinstance(result, ToolResult)
    assert result.ok and result.data.tools == []
    assert result.data.error == "bridge_access_denied"
