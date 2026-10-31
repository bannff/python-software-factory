"""Runtime module for MCP server aggregation."""

from .discovery import BrickDiscovery, BrickInfo
from .aggregator import MCPAggregator
from .lazy_loader import LazyBrickLoader

__all__ = ["BrickDiscovery", "BrickInfo", "MCPAggregator", "LazyBrickLoader"]
