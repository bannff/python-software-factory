"""Tests for security MCP contract compliance."""

import asyncio

import pytest

from factory.security.runtime.adapters.mock import MockAnalyzerAdapter
from factory.security.runtime.runtime import SecurityRuntime
from factory.security.interface import Runtime, create_server


class TestMCPContract:
    """Test MCP contract compliance."""

    @pytest.fixture
    def runtime(self) -> SecurityRuntime:
        """Create runtime with mock adapter."""
        return Runtime(MockAnalyzerAdapter())

    @pytest.fixture
    def mcp(self, runtime: SecurityRuntime):
        """Create MCP server."""
        return create_server(runtime)

    def test_interface_exports(self) -> None:
        """Test interface exports Runtime and create_server."""
        assert Runtime is not None
        assert create_server is not None

    def test_mcp_server_created(self, mcp) -> None:
        """Test MCP server is created."""
        assert mcp is not None
        assert mcp.name == "security-module"

    def test_has_contract_tools(self, mcp) -> None:
        """Test MCP server has required contract tools."""
        tool_names = [t.name for t in asyncio.run(mcp.list_tools())]
        assert "security.get_capabilities" in tool_names
        assert "security.health_check" in tool_names
        assert "security.describe_config_schema" in tool_names

    def test_has_operational_tools(self, mcp) -> None:
        """Test MCP server has operational tools."""
        tool_names = [t.name for t in asyncio.run(mcp.list_tools())]
        assert "security.analyze" in tool_names
        assert "security.threat_model" in tool_names


class TestContractToolBehavior:
    """Test contract tool behavior."""

    @pytest.fixture
    def runtime(self) -> SecurityRuntime:
        """Create runtime with mock adapter."""
        return Runtime(MockAnalyzerAdapter())

    @pytest.fixture
    def mcp(self, runtime: SecurityRuntime):
        """Create MCP server."""
        return create_server(runtime)

    def test_get_capabilities(self, mcp) -> None:
        """Test get_capabilities returns expected structure."""
        tool = asyncio.run(mcp.get_tool("security.get_capabilities"))
        result = tool.fn()
        assert result.ok is True
        assert result.data.name == "security"
        assert result.data.version
        assert result.data.tools
        assert result.data.adapters

    def test_health_check(self, mcp) -> None:
        """Test health_check returns health status."""
        tool = asyncio.run(mcp.get_tool("security.health_check"))
        result = tool.fn()
        assert result.ok is True
        assert result.data.healthy is True

    def test_describe_config_schema(self, mcp) -> None:
        """Test describe_config_schema returns JSON schema."""
        tool = asyncio.run(mcp.get_tool("security.describe_config_schema"))
        result = tool.fn()
        assert result.ok is True
        assert result.data.type == "object"
        assert "max_findings" in result.data.properties

    def test_has_authoring_tools(self, mcp) -> None:
        """Test MCP server has authoring tools."""
        tool_names = [t.name for t in asyncio.run(mcp.list_tools())]
        assert "security.authoring.get_status" in tool_names
        assert "security.authoring.list_rules" in tool_names
        assert "security.authoring.upsert_rule" in tool_names
        assert "security.authoring.delete_rule" in tool_names


def test_list_findings_for_run_returns_error_envelope_for_failed_graph_result(monkeypatch) -> None:
    from factory.mcp_utils.runtime.tool_catalog import ToolCatalog
    from factory.mcp_utils.runtime.tool_result import ToolResult
    from factory.security.mcp.operational import register

    class _Aggregator:
        def invoke_tool(self, *_args, **_kwargs):
            return ToolResult(ok=False, data=None, error="graph unavailable")

    monkeypatch.setattr("factory.mcp_server.interface.get_server", lambda: None)
    monkeypatch.setattr("factory.mcp_server.interface.get_aggregator", lambda: _Aggregator())
    mcp = ToolCatalog("security-failure-test")
    register(mcp, Runtime(MockAnalyzerAdapter()))
    tool = asyncio.run(mcp.get_tool("security_list_findings_for_run"))

    result = tool.fn(run_id="run-failed")
    assert result.ok is True
    assert result.data.error == "graph unavailable"
    assert result.data.rows == []
