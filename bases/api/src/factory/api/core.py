"""Core types and models for API base."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class AdapterType(str, Enum):
    """Supported API adapter types."""

    REST = "rest"
    GRAPHQL = "graphql"


@dataclass
class RouteInfo:
    """Information about a registered route."""

    path: str
    method: str
    handler: str
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "path": self.path,
            "method": self.method,
            "handler": self.handler,
            "tags": self.tags,
        }


@dataclass
class APIHealth:
    """Health status for API."""

    healthy: bool
    adapter: str
    routes_count: int
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "healthy": self.healthy,
            "adapter": self.adapter,
            "routes_count": self.routes_count,
            "error": self.error,
        }
