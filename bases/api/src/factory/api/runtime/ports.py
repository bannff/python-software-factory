"""API ports - Protocol interfaces for API adapters.

Defines abstract interfaces that API adapters must implement.
"""

from __future__ import annotations

from typing import Any, Callable, Protocol, runtime_checkable

from ..core import APIHealth, RouteInfo


@runtime_checkable
class APIAdapterPort(Protocol):
    """Port: API adapter (REST, GraphQL, etc.)"""

    @property
    def adapter_type(self) -> str:
        """Unique identifier for this adapter type."""
        ...

    def add_route(
        self,
        path: str,
        method: str,
        handler: Callable[..., Any],
        tags: list[str] | None = None,
    ) -> None:
        """Register a route with the API."""
        ...

    def list_routes(self) -> list[RouteInfo]:
        """List all registered routes."""
        ...

    def get_app(self) -> Any:
        """Get the underlying application instance."""
        ...

    def health_check(self) -> APIHealth:
        """Check adapter health."""
        ...
