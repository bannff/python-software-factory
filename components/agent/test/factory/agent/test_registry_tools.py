"""Tests for Tool registry."""

import pytest
from pathlib import Path
import tempfile

from factory.agent.registry.tools import ToolRegistry


@pytest.fixture
def temp_tools_dir():
    """Create a temporary tools directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tools_dir = Path(tmpdir)

        (tools_dir / "__init__.py").write_text("")
        (tools_dir / "custom_tools.py").write_text("""
from factory.agent.registry.tools import tool

@tool
def test_tool(arg: str) -> dict:
    '''A test tool.'''
    return {"result": arg}
""")

        yield tools_dir


class TestToolRegistry:
    """Tests for ToolRegistry."""

    @pytest.mark.asyncio
    async def test_load_tools(self, temp_tools_dir):
        """Test loading tools from directory."""
        registry = ToolRegistry(temp_tools_dir)
        await registry.load()

        assert "test_tool" in registry.tools

    @pytest.mark.asyncio
    async def test_register_tool(self, temp_tools_dir):
        """Test registering tools programmatically."""
        registry = ToolRegistry(temp_tools_dir)

        def my_tool(x: int) -> int:
            return x * 2

        registry.register("my_tool", my_tool)
        assert "my_tool" in registry.tools

    @pytest.mark.asyncio
    async def test_call_tool(self, temp_tools_dir):
        """Test calling a registered tool."""
        registry = ToolRegistry(temp_tools_dir)

        def add(a: int, b: int) -> int:
            return a + b

        registry.register("add", add)
        result = registry.call("add", a=2, b=3)
        assert result == 5

    @pytest.mark.asyncio
    async def test_list_tools(self, temp_tools_dir):
        """Test listing all tools."""
        registry = ToolRegistry(temp_tools_dir)

        def my_tool(arg: str) -> dict:
            """My tool description."""
            return {"result": arg}

        registry.register("my_tool", my_tool)

        tools = registry.list_tools()
        assert len(tools) == 1
        assert tools[0]["name"] == "my_tool"
        assert "My tool description" in tools[0]["description"]
