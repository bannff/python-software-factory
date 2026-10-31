"""MCP Server ports - Protocol interfaces for brick aggregation.

Defines abstract interfaces for brick discovery and aggregation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


@dataclass
class BrickInfo:
    """Information about a registered brick."""

    name: str
    namespace: str
    tools_count: int
    healthy: bool
    error: str | None = None


@runtime_checkable
class BrickDiscoveryPort(Protocol):
    """Port: Brick discovery backend."""

    def discover_bricks(self) -> list[str]:
        """Discover available brick names."""
        ...

    def get_brick_metadata(self, name: str) -> dict[str, Any] | None:
        """Get metadata for a specific brick."""
        ...


@runtime_checkable
class BrickAggregatorPort(Protocol):
    """Port: Brick aggregation backend."""

    def register_brick(self, brick_name: str) -> bool:
        """Register a brick's tools into the aggregator."""
        ...

    def register_all(self, brick_names: list[str]) -> dict[str, bool]:
        """Register multiple bricks."""
        ...

    def get_registered_bricks(self) -> list[BrickInfo]:
        """Get list of registered bricks."""
        ...

    def get_aggregated_capabilities(self) -> dict[str, Any]:
        """Get combined capabilities from all registered bricks."""
        ...

    def aggregated_health_check(self) -> dict[str, Any]:
        """Check health of all registered bricks."""
        ...
