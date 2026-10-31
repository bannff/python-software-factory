"""Tests for mcp_utils.tools — shared tool map extraction."""

from __future__ import annotations

from factory.mcp_utils.runtime.tool_catalog import ToolCatalog

from factory.mcp_utils.interface import get_tool_map


class TestGetToolMap:
    """Test the shared get_tool_map utility."""

    def test_extracts_tools_from_mcp(self):
        mcp = ToolCatalog("test")

        @mcp.tool()
        def kb_search(query: str) -> dict:
            return {"mock": True}

        @mcp.tool()
        def health_check() -> dict:
            return {"healthy": True}

        result = get_tool_map(mcp)
        assert "kb_search" in result
        assert "health_check" in result
        assert len(result) == 2

    def test_returns_empty_for_none(self):
        assert get_tool_map(None) == {}

    def test_callable_functions(self):
        mcp = ToolCatalog("test")

        @mcp.tool()
        def greet(name: str) -> str:
            return f"hello {name}"

        result = get_tool_map(mcp)
        assert result["greet"]("world") == "hello world"
