"""Behavior tests for API authoring MCP tools."""

from __future__ import annotations

import asyncio

import pytest
from factory.api.runtime.runtime import APIRuntime, reset_runtime
from factory.api.server import create_mcp_server
from factory.mcp_utils.runtime.tool_result import ToolResult


@pytest.fixture(params=[True, False])
def mcp_server(request):
    reset_runtime()
    server = create_mcp_server(APIRuntime(), enable_authoring=request.param)
    yield server, request.param
    reset_runtime()


def _get_tool(server, name: str):
    return asyncio.run(server.get_tool(name))


def test_authoring_status_is_registered_and_typed(mcp_server) -> None:
    server, enabled = mcp_server
    result = _get_tool(server, "api.authoring.get_status").fn()
    assert isinstance(result, ToolResult) and result.ok
    assert result.data.enabled is enabled


def test_set_config_preserves_authoring_gate(mcp_server) -> None:
    server, enabled = mcp_server
    result = _get_tool(server, "api.authoring.set_config").fn(adapter_type="graphql")
    assert result.ok
    assert result.data.updated is enabled
    if enabled:
        assert result.data.changes.adapter == "graphql"
    else:
        assert result.data.error == "Authoring is disabled"


def test_reset_routes_preserves_authoring_gate(mcp_server) -> None:
    server, enabled = mcp_server
    result = _get_tool(server, "api.authoring.reset_routes").fn()
    assert result.ok
    assert result.data.reset is enabled
    if not enabled:
        assert result.data.error == "Authoring is disabled"
