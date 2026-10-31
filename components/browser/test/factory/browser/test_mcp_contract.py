"""Tests for Browser FastMCP public contracts."""

import asyncio
from inspect import signature

import pytest

from factory.browser.interface import Runtime, create_server
from factory.browser.runtime.adapters.mock import MockAdapter
from factory.browser.runtime.runtime import BrowserRuntime
from factory.mcp_utils.interface import ToolResult


class TestMCPContract:
    """Test MCP server discovery and typed public contract metadata."""

    @pytest.fixture
    def runtime(self) -> BrowserRuntime:
        return Runtime(MockAdapter())

    @pytest.fixture
    def mcp(self, runtime: BrowserRuntime):
        return create_server(runtime)

    def test_interface_exports(self) -> None:
        assert Runtime is not None
        assert create_server is not None

    def test_mcp_server_created(self, mcp) -> None:
        assert mcp.name == "browser-module"

    def test_has_contract_tools(self, mcp) -> None:
        tool_names = [tool.name for tool in asyncio.run(mcp.list_tools())]
        assert "browser.get_capabilities" in tool_names
        assert "browser.health_check" in tool_names
        assert "browser.describe_config_schema" in tool_names

    def test_has_operational_tools(self, mcp) -> None:
        tool_names = [tool.name for tool in asyncio.run(mcp.list_tools())]
        assert {
            "browser.launch", "browser.close", "browser.navigate",
            "browser.click", "browser.type_text", "browser.screenshot",
            "browser.evaluate", "browser.get_content", "browser.wait_for_selector",
        }.issubset(tool_names)

    def test_has_deterministic_tools(self, mcp) -> None:
        tool_names = [tool.name for tool in asyncio.run(mcp.list_tools())]
        assert {"browser.list_sessions", "browser.get_session"}.issubset(tool_names)

    def test_all_tools_have_strict_same_brick_contracts(self, mcp) -> None:
        tools = asyncio.run(mcp.list_tools())
        assert len(tools) == 20
        assert sum(tool.fn._mcp_category == "deterministic" for tool in tools) == 6
        assert sum(tool.fn._mcp_category == "operational" for tool in tools) == 10
        assert sum(tool.fn._mcp_category == "authoring" for tool in tools) == 4
        for tool in tools:
            input_model = tool.fn._mcp_input_model
            output_model = tool.fn._mcp_output_model
            assert input_model.__module__.startswith("factory.browser.mcp.contracts")
            assert output_model.__module__.startswith("factory.browser.mcp.contracts")
            assert input_model.model_config.get("extra") == "forbid"
            assert input_model.model_config.get("strict") is True
            assert str(signature(tool.fn).return_annotation) == (
                f"ToolResult[{output_model.__name__}]"
            )

    def test_has_authoring_tools(self, mcp) -> None:
        tool_names = [tool.name for tool in asyncio.run(mcp.list_tools())]
        assert {
            "browser.authoring.get_status", "browser.authoring.list_profiles",
            "browser.authoring.upsert_profile", "browser.authoring.delete_profile",
        }.issubset(tool_names)


class TestContractToolBehavior:
    """Test typed public outputs and strict flat-kwargs ingress."""

    @pytest.fixture
    def runtime(self) -> BrowserRuntime:
        return Runtime(MockAdapter())

    @pytest.fixture
    def mcp(self, runtime: BrowserRuntime):
        return create_server(runtime)

    def test_get_capabilities(self, mcp) -> None:
        tool = asyncio.run(mcp.get_tool("browser.get_capabilities"))
        result = tool.fn()
        assert isinstance(result, ToolResult) and result.ok
        assert result.data.name == "browser"
        assert result.data.version
        assert result.data.tools and result.data.adapters and result.data.features

    def test_health_check(self, mcp) -> None:
        tool = asyncio.run(mcp.get_tool("browser.health_check"))
        result = tool.fn()
        assert result.ok and result.data.healthy is True

    def test_describe_config_schema(self, mcp) -> None:
        tool = asyncio.run(mcp.get_tool("browser.describe_config_schema"))
        result = tool.fn()
        assert result.ok and result.data.type == "object"
        assert "headless" in result.data.properties.root

    def test_strict_ingress_and_normal_session_miss(self, mcp) -> None:
        tool = asyncio.run(mcp.get_tool("browser.get_session"))
        result = tool.fn(session_id="missing")
        assert result.ok and result.data.found is False
        with pytest.raises(Exception):
            tool.fn(session_id="missing", unexpected=True)
