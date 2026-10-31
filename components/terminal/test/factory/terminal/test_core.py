"""Terminal MCP catalog contract checks."""
from __future__ import annotations

import asyncio

from factory.terminal.runtime.runtime import TerminalRuntime
from factory.terminal.server import create_tool_catalog


EXPECTED = {
    "terminal_list", "terminal_list_shells", "terminal_open_session",
    "terminal_write", "terminal_read", "terminal_resize", "terminal_close",
}


def test_terminal_catalog_has_exact_typed_surface() -> None:
    catalog = create_tool_catalog(TerminalRuntime())
    tools = asyncio.run(catalog.list_tools())
    assert {tool.name for tool in tools} == EXPECTED
    for tool in tools:
        assert getattr(tool.fn, "_mcp_input_model").model_config["extra"] == "forbid"
        assert getattr(tool.fn, "_mcp_output_model") is not None
        assert getattr(tool.fn, "_mcp_category") in {"deterministic", "operational"}
