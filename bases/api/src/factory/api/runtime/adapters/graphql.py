"""GraphQL API adapter (stub for future implementation)."""

from __future__ import annotations

from typing import Any, Callable

from ...core import APIHealth, RouteInfo


class GraphQLAdapter:
    """GraphQL API adapter (stub).

    Future implementation will use Strawberry or Ariadne.
    """

    def __init__(self) -> None:
        self._schema: Any = None
        self._routes: list[RouteInfo] = []

    @property
    def adapter_type(self) -> str:
        """Return adapter type identifier."""
        return "graphql"

    def add_route(
        self,
        path: str,
        method: str,
        handler: Callable[..., Any],
        tags: list[str] | None = None,
    ) -> None:
        """Register a GraphQL resolver (stub)."""
        route_info = RouteInfo(
            path=path,
            method="QUERY" if method.upper() == "GET" else "MUTATION",
            handler=handler.__name__,
            tags=tags or [],
        )
        self._routes.append(route_info)

    def list_routes(self) -> list[RouteInfo]:
        """List all registered resolvers."""
        return self._routes.copy()

    def get_app(self) -> Any:
        """Get the GraphQL schema/app."""
        return self._schema

    def health_check(self) -> APIHealth:
        """Check adapter health."""
        return APIHealth(
            healthy=True,
            adapter="graphql",
            routes_count=len(self._routes),
            error=None,
        )
