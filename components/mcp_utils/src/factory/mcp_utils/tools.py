"""Shared utilities for extracting tools from FastMCP server instances.

Uses the public ``list_tools()`` / ``get_tool()`` API (FastMCP 3.x).
"""

from __future__ import annotations

import asyncio
import concurrent.futures
from typing import Any, Callable


def _run_sync(coro: Any) -> Any:
    """Resolve an awaitable synchronously."""
    if not hasattr(coro, "__await__"):
        return coro
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        with concurrent.futures.ThreadPoolExecutor() as pool:
            return pool.submit(asyncio.run, coro).result()
    return asyncio.run(coro)


def get_tool_map(mcp_server: Any) -> dict[str, Callable[..., Any]]:
    """Extract tool name→function map from a FastMCP server instance.

    Uses the public ``list_tools()`` and ``get_tool()`` APIs so we
    don't depend on FastMCP internals.

    Args:
        mcp_server: A FastMCP instance (or None).

    Returns:
        Dict mapping tool names to their callable functions.
    """
    if mcp_server is None:
        return {}
    tools: dict[str, Callable[..., Any]] = {}
    tool_list = _run_sync(mcp_server.list_tools())
    if not tool_list:
        return tools
    for info in tool_list:
        tool = _run_sync(mcp_server.get_tool(info.name))
        fn = getattr(tool, "fn", None) if tool else None
        if fn is not None:
            tools[info.name] = fn
    return tools
