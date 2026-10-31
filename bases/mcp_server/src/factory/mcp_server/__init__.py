"""MCP Server Aggregator - Unified entry point for all factory bricks."""

from .interface import (
    create_server,
    create_mcp_server,
    get_server,
    get_aggregator,
    main,
    BrickDiscovery,
    BrickInfo,
    MCPAggregator,
)

__all__ = [
    "create_server",
    "create_mcp_server",
    "get_server",
    "get_aggregator",
    "main",
    "BrickDiscovery",
    "BrickInfo",
    "MCPAggregator",
]
