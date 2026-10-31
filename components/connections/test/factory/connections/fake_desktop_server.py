"""Fake desktop-automation MCP server exposing computer_* tool names (tests only)."""
from __future__ import annotations

from mcp.server.mcpserver import MCPServer

server = MCPServer("fake-computer")


@server.tool()
def computer_list_apps() -> str:
    """List on-screen apps (fake)."""
    return "Finder"


@server.tool()
def computer_get_state(app: str) -> str:
    """Snapshot a window (fake)."""
    return f"0 window {app}"


@server.tool()
def computer_click(app: str, element_index: int) -> str:
    """Click an element (fake)."""
    return f"clicked {app}#{element_index}"


if __name__ == "__main__":
    server.run(transport="stdio")
