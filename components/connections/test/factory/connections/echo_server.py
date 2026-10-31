"""Minimal real MCP stdio server used only by tests (run as a subprocess)."""
from __future__ import annotations

import os

from mcp.server.mcpserver import MCPServer

server = MCPServer("echo-fixture")


@server.tool()
def echo(text: str) -> str:
    """Echo text back."""
    return f"echo:{text}"


@server.tool()
def read_env(name: str) -> str:
    """Return the named environment variable or '<unset>'."""
    return os.environ.get(name, "<unset>")


if __name__ == "__main__":
    server.run(transport="stdio")
