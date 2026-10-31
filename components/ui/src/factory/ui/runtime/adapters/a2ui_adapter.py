"""A2UI Protocol adapter.

Renders A2UI payloads through existing adapters (HTMX, React).
Supports incremental updates for streaming.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from .base import RenderAdapter, RenderResult
from ..models import UIComponent, UIView
from ..a2ui import a2ui_to_ui_view, validate_a2ui, get_supported_components


@dataclass
class A2UIConfig:
    """Configuration for A2UI adapter."""

    render_backend: Literal["htmx", "react", "json"] = "htmx"
    strict_validation: bool = True
    include_metadata: bool = True


class A2UIAdapter(RenderAdapter):
    """Adapter for A2UI protocol.

    Transforms A2UI payloads into native UI, then delegates
    to HTMX or React adapter for final rendering.
    """

    def __init__(
        self,
        backend_adapter: RenderAdapter,
        config: A2UIConfig | None = None,
    ) -> None:
        self._backend = backend_adapter
        self._config = config or A2UIConfig()
        self._pending_updates: list[dict[str, Any]] = []

    @property
    def adapter_type(self) -> str:
        return f"a2ui-{self._backend.adapter_type}"

    @property
    def content_type(self) -> str:
        return self._backend.content_type

    def render_view(self, view: UIView) -> RenderResult:
        """Render a UIView (delegates to backend)."""
        result = self._backend.render_view(view)
        result.metadata["a2ui"] = True
        return result

    def render_component(self, component: UIComponent) -> RenderResult:
        """Render a single component (delegates to backend)."""
        result = self._backend.render_component(component)
        result.metadata["a2ui"] = True
        return result

    def render_a2ui(self, payload: dict[str, Any]) -> RenderResult:
        """Render A2UI payload directly.

        Args:
            payload: A2UI JSON payload from agent

        Returns:
            RenderResult with rendered content

        Raises:
            ValueError: If validation fails and strict_validation is True
        """
        # Validate
        if self._config.strict_validation:
            errors = validate_a2ui(payload)
            if errors:
                error_msgs = [f"{e.path}: {e.message}" for e in errors]
                raise ValueError(f"A2UI validation failed: {error_msgs}")

        # Convert to native view
        view = a2ui_to_ui_view(payload)

        # Render through backend
        result = self._backend.render_view(view)
        result.metadata["a2ui"] = True
        result.metadata["a2ui_version"] = payload.get("version", "0.8")

        return result

    def supports_streaming(self) -> bool:
        """A2UI supports incremental updates."""
        return True

    def apply_update(self, update: dict[str, Any]) -> RenderResult | None:
        """Apply incremental A2UI update.

        A2UI supports streaming updates where components can be
        added, modified, or removed incrementally.

        Args:
            update: Incremental update with action and component data

        Returns:
            RenderResult for the updated component, or None if buffered
        """
        action = update.get("action", "add")
        component_data = update.get("component", {})

        if action == "add":
            # Convert single component
            from ..a2ui.schema import A2UIComponent
            a2ui_comp = A2UIComponent.from_dict(component_data)
            # Store for batch rendering
            self._pending_updates.append(update)
            return None

        elif action == "flush":
            # Render all pending updates
            if not self._pending_updates:
                return None

            components = [u.get("component", {}) for u in self._pending_updates]
            payload = {"components": components}
            self._pending_updates.clear()
            return self.render_a2ui(payload)

        return None

    def get_component_catalog(self) -> list[dict[str, Any]]:
        """Get supported A2UI component types."""
        return get_supported_components()


def create_a2ui_adapter(
    backend: Literal["htmx", "react", "json"] = "htmx",
    config: A2UIConfig | None = None,
) -> A2UIAdapter:
    """Factory function to create A2UI adapter with specified backend.

    Args:
        backend: Which render backend to use
        config: Optional configuration

    Returns:
        Configured A2UIAdapter
    """
    if backend == "htmx":
        from .htmx_adapter import HTMXAdapter
        backend_adapter = HTMXAdapter()
    elif backend == "react":
        from .react_adapter import ReactAdapter
        backend_adapter = ReactAdapter()
    else:
        from .json_adapter import JsonAdapter
        backend_adapter = JsonAdapter()

    return A2UIAdapter(backend_adapter, config)
