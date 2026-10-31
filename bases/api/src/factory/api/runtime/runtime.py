"""API runtime - adapter factory and management."""

from __future__ import annotations

from typing import Any, Callable

from ..core import AdapterType, APIHealth, RouteInfo
from .ports import APIAdapterPort


class APIRuntime:
    """Runtime for managing API adapters."""

    def __init__(self, adapter_type: str = "rest") -> None:
        self._adapter_type = AdapterType(adapter_type)
        self._adapter: APIAdapterPort | None = None

    @staticmethod
    def available_backends() -> list[str]:
        """List available API backends."""
        return ["rest", "graphql"]

    def get_adapter(self) -> APIAdapterPort:
        """Get or create the API adapter."""
        if self._adapter is None:
            self._adapter = self._create_adapter()
        return self._adapter

    def _create_adapter(self) -> APIAdapterPort:
        """Create adapter based on type."""
        if self._adapter_type == AdapterType.REST:
            from .adapters.rest import RESTAdapter
            return RESTAdapter()
        elif self._adapter_type == AdapterType.GRAPHQL:
            from .adapters.graphql import GraphQLAdapter
            return GraphQLAdapter()
        else:
            raise ValueError(f"Unknown adapter type: {self._adapter_type}")

    def add_route(
        self,
        path: str,
        method: str,
        handler: Callable[..., Any],
        tags: list[str] | None = None,
    ) -> None:
        """Register a route."""
        self.get_adapter().add_route(path, method, handler, tags)

    def list_routes(self) -> list[RouteInfo]:
        """List all routes."""
        return self.get_adapter().list_routes()

    def get_app(self) -> Any:
        """Get the underlying app."""
        return self.get_adapter().get_app()

    def health_check(self) -> APIHealth:
        """Check runtime health."""
        return self.get_adapter().health_check()

    def get_openapi_schema(self) -> dict[str, Any]:
        """Get OpenAPI schema (REST adapter only)."""
        adapter = self.get_adapter()
        if hasattr(adapter, "get_openapi_schema"):
            return adapter.get_openapi_schema()
        return {"error": "OpenAPI not supported by this adapter"}


_runtime: APIRuntime | None = None


def get_runtime(adapter_type: str = "rest") -> APIRuntime:
    """Get the global API runtime."""
    global _runtime
    if _runtime is None:
        _runtime = APIRuntime(adapter_type)
    return _runtime


def reset_runtime() -> None:
    """Reset the global runtime (for testing)."""
    global _runtime
    _runtime = None
