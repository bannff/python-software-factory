"""Hybrid adapter for route-based renderer selection.

Allows different parts of an application to use different rendering
strategies based on URL patterns. For example:
- /admin/* → HTMX (fast, simple agent-facing)
- /app/* → React (polished user-facing)
- /api/ui/* → JSON (API consumption)
"""

from typing import Any

from ..models import UIComponent, UIView
from .base import RenderAdapter, RenderResult
from .htmx_adapter import HTMXAdapter
from .react_adapter import ReactAdapter
from .json_adapter import JsonAdapter


class HybridAdapter(RenderAdapter):
    """Route-based adapter selection.

    Delegates rendering to the appropriate adapter based on route patterns.
    Useful for applications that need both server-rendered and SPA sections.
    """

    def __init__(
        self,
        route_map: dict[str, str] | None = None,
        default_adapter: str = "json",
    ) -> None:
        """Initialize hybrid adapter.

        Args:
            route_map: Mapping of route patterns to adapter types.
                       Patterns support wildcards (*).
                       Example: {"/admin/*": "htmx", "/app/*": "react"}
            default_adapter: Adapter to use when no pattern matches.
        """
        self._route_map = route_map or {
            "/admin/*": "htmx",
            "/dashboard/*": "htmx",
            "/app/*": "react",
            "/api/ui/*": "json",
        }
        self._default = default_adapter
        self._current_route: str | None = None

        # Initialize child adapters
        self._adapters: dict[str, RenderAdapter] = {
            "htmx": HTMXAdapter(),
            "react": ReactAdapter(),
            "json": JsonAdapter(),
        }

    @property
    def adapter_type(self) -> str:
        return "hybrid"

    @property
    def content_type(self) -> str:
        # Delegate to selected adapter
        adapter = self._get_adapter_for_route(self._current_route)
        return adapter.content_type

    def set_route(self, route: str) -> None:
        """Set the current route for adapter selection."""
        self._current_route = route

    def render_view(self, view: UIView, route: str | None = None) -> RenderResult:
        """Render view using route-appropriate adapter."""
        effective_route = route or self._current_route
        adapter = self._get_adapter_for_route(effective_route)
        result = adapter.render_view(view)

        # Add hybrid metadata
        result.metadata["hybrid_route"] = effective_route
        result.metadata["selected_adapter"] = adapter.adapter_type
        return result

    def render_component(self, component: UIComponent) -> RenderResult:
        """Render component using current route's adapter."""
        adapter = self._get_adapter_for_route(self._current_route)
        return adapter.render_component(component)

    def supports_streaming(self) -> bool:
        return True

    def get_adapter(self, adapter_type: str) -> RenderAdapter | None:
        """Get a specific child adapter."""
        return self._adapters.get(adapter_type)

    def register_adapter(self, name: str, adapter: RenderAdapter) -> None:
        """Register a custom adapter."""
        self._adapters[name] = adapter

    def get_route_map(self) -> dict[str, str]:
        """Get current route-to-adapter mapping."""
        return dict(self._route_map)

    def set_route_map(self, route_map: dict[str, str]) -> None:
        """Update route-to-adapter mapping."""
        self._route_map = route_map

    def _get_adapter_for_route(self, route: str | None) -> RenderAdapter:
        """Select adapter based on route pattern matching."""
        if not route:
            return self._adapters.get(self._default, self._adapters["json"])

        for pattern, adapter_name in self._route_map.items():
            if self._matches_pattern(route, pattern):
                adapter = self._adapters.get(adapter_name)
                if adapter:
                    return adapter

        return self._adapters.get(self._default, self._adapters["json"])

    def _matches_pattern(self, route: str, pattern: str) -> bool:
        """Check if route matches pattern (supports * wildcard)."""
        if pattern.endswith("/*"):
            prefix = pattern[:-2]
            return route.startswith(prefix)
        if pattern.endswith("*"):
            prefix = pattern[:-1]
            return route.startswith(prefix)
        return route == pattern

    def to_dict(self) -> dict[str, Any]:
        """Serialize adapter configuration."""
        return {
            "adapter_type": self.adapter_type,
            "route_map": self._route_map,
            "default_adapter": self._default,
            "available_adapters": list(self._adapters.keys()),
            "current_route": self._current_route,
        }
