"""Behavior tests for API operational MCP tools."""

from __future__ import annotations

import asyncio

import pytest
from factory.api.runtime.runtime import APIRuntime, reset_runtime
from factory.api.server import create_mcp_server
from factory.mcp_utils.runtime.tool_result import ToolResult


@pytest.fixture()
def mcp_server():
    reset_runtime()
    server = create_mcp_server(APIRuntime())
    yield server
    reset_runtime()


def _get_tool(server, name: str):
    return asyncio.run(server.get_tool(name))


def test_add_route_returns_typed_route_registration(mcp_server) -> None:
    result = _get_tool(mcp_server, "api.add_route").fn(
        path="/users", method="GET", handler_name="get_users",
    )
    assert isinstance(result, ToolResult) and result.ok
    assert result.data.registered and result.data.path == "/users"


def test_remove_route_preserves_unsupported_adapter_outcome(mcp_server) -> None:
    result = _get_tool(mcp_server, "api.remove_route").fn(path="/nonexistent")
    assert result.ok and not result.data.removed
    assert result.data.reason == "Adapter does not support route removal"


def test_switch_adapter_returns_typed_success_and_negative_outcome(mcp_server) -> None:
    switch = _get_tool(mcp_server, "api.switch_adapter")
    switched = switch.fn(adapter_type="graphql")
    rejected = switch.fn(adapter_type="grpc")
    assert switched.ok and switched.data.adapter == "graphql"
    assert rejected.ok and rejected.data.error == "Unknown adapter: grpc"
