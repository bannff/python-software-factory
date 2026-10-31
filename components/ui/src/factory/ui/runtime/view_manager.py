"""View manager - orchestrates UI operations."""

import uuid
from typing import Any

from .adapters.base import RenderAdapter, RenderResult
from .adapters.json_adapter import JsonAdapter
from .adapters.inline_html_adapter import InlineHtmlRenderAdapter
from .adapters.htmx_adapter import HTMXAdapter
from .adapters.react_adapter import ReactAdapter
from .adapters.hybrid_adapter import HybridAdapter
from .adapters.a2ui_adapter import A2UIAdapter

try:
    from .adapters.flet_adapter import FletAdapter
except ImportError:
    FletAdapter = None  # type: ignore[assignment,misc]
from .adapters.ag_ui_adapter import AGUIAdapter
from .models import ComponentType, UIComponent, UIView
from .push_channel import PushChannel
from .registry import ComponentRegistry
from .store.view_store import InMemoryViewStore
from .view_manager_ops import ViewComponentOps


class ViewManager:
    """Central manager for UI views and components."""

    def __init__(
        self, store: InMemoryViewStore | None = None,
        push_channel: PushChannel | None = None,
        registry: ComponentRegistry | None = None,
        default_adapter: str = "json",
    ) -> None:
        self.store = store or InMemoryViewStore()
        self.push_channel = push_channel or PushChannel()
        self.registry = registry or ComponentRegistry()
        self._default_adapter = default_adapter
        self._adapters: dict[str, RenderAdapter] = self._init_adapters()
        self._ops = ViewComponentOps(self)

    def _init_adapters(self) -> dict[str, RenderAdapter]:
        """Initialize all available adapters.

        A2UI is the default protocol layer — every styling adapter is
        wrapped with A2UIAdapter so agents can emit A2UI payloads and
        have them rendered through any backend. Direct adapter names
        (htmx, react, flet) resolve to their A2UI-wrapped versions.
        """
        json_adapter = JsonAdapter()
        inline_html_adapter = InlineHtmlRenderAdapter()
        htmx_adapter = HTMXAdapter()
        react_adapter = ReactAdapter()
        ag_ui_adapter = AGUIAdapter()

        # A2UI-wrapped versions (standard for all rendering)
        a2ui_htmx = A2UIAdapter(htmx_adapter)
        a2ui_react = A2UIAdapter(react_adapter)
        a2ui_json = A2UIAdapter(json_adapter)
        a2ui_ag_ui = A2UIAdapter(ag_ui_adapter)

        adapters: dict[str, RenderAdapter] = {
            # Primary names resolve to A2UI-wrapped adapters
            "htmx": a2ui_htmx,
            "react": a2ui_react,
            # Explicit A2UI names for clarity
            "a2ui-htmx": a2ui_htmx,
            "a2ui-react": a2ui_react,
            "a2ui-json": a2ui_json,
            "a2ui-ag-ui": a2ui_ag_ui,
            # Non-visual adapters (no A2UI wrapping needed)
            "json": json_adapter,
            "inline-html": inline_html_adapter,
            "hybrid": HybridAdapter(),
            # AG-UI streaming protocol adapter
            "ag-ui": ag_ui_adapter,
        }

        # Flet adapter is optional — requires flet package
        if FletAdapter is not None:
            flet_adapter = FletAdapter()
            a2ui_flet = A2UIAdapter(flet_adapter)
            adapters["flet"] = a2ui_flet
            adapters["a2ui-flet"] = a2ui_flet

        return adapters

    def register_adapter(self, adapter: RenderAdapter) -> None:
        self._adapters[adapter.adapter_type] = adapter

    def get_adapter(self, adapter_type: str) -> RenderAdapter | None:
        return self._adapters.get(adapter_type)

    def list_adapters(self) -> list[dict[str, Any]]:
        """List adapters with metadata."""
        return [
            {"type": a.adapter_type, "content_type": a.content_type, "streaming": a.supports_streaming()}
            for a in self._adapters.values()
        ]

    def create_view(
        self, name: str, view_id: str | None = None,
        layout: dict[str, Any] | None = None, metadata: dict[str, Any] | None = None,
    ) -> UIView:
        view = UIView(id=view_id or str(uuid.uuid4()), name=name, layout=layout or {}, metadata=metadata or {})
        self.store.save(view)
        return view

    def get_view(self, view_id: str) -> UIView | None:
        return self.store.get(view_id)

    def delete_view(self, view_id: str) -> bool:
        return self.store.delete(view_id)

    def list_views(self) -> list[UIView]:
        return self.store.get_all()

    def create_component(
        self, component_type: str | ComponentType, props: dict[str, Any] | None = None,
        styles: dict[str, str] | None = None, component_id: str | None = None,
    ) -> UIComponent:
        if isinstance(component_type, str):
            component_type = ComponentType(component_type)
        return self.registry.create_component(
            component_id=component_id or str(uuid.uuid4()),
            component_type=component_type, props=props, styles=styles,
        )

    async def add_component(self, view_id: str, component: UIComponent, position: int | None = None):
        return await self._ops.add_component(view_id, component, position)

    async def update_component(
        self, view_id: str, component_id: str,
        props: dict[str, Any] | None = None, styles: dict[str, str] | None = None,
    ):
        return await self._ops.update_component(view_id, component_id, props, styles)

    async def remove_component(self, view_id: str, component_id: str) -> bool:
        return await self._ops.remove_component(view_id, component_id)

    async def push_view(self, view_id: str) -> int:
        return await self._ops.push_view(view_id)

    def render(self, view_id: str, adapter_type: str | None = None, route: str | None = None) -> RenderResult | None:
        view = self.store.get(view_id)
        if not view:
            return None
        adapter_type = adapter_type or self._default_adapter
        adapter = self._adapters.get(adapter_type)
        if not adapter:
            return None
        # Hybrid adapter supports route-based selection
        if adapter_type == "hybrid" and route and isinstance(adapter, HybridAdapter):
            return adapter.render_view(view, route=route)
        return adapter.render_view(view)

    def render_component(self, component: UIComponent, adapter_type: str | None = None) -> RenderResult | None:
        adapter_type = adapter_type or self._default_adapter
        adapter = self._adapters.get(adapter_type)
        return adapter.render_component(component) if adapter else None

    def get_panels_for_brick(self, brick: str) -> list[UIView]:
        """Return all panel views declared by a specific brick."""
        return [v for v in self.store.get_all()
                if v.metadata.get("brick") == brick
                or any(c.props.get("brick") == brick for c in v.components)]

    def get_panel_size_hint(self, view_id: str) -> str:
        """Return the size_hint for a panel, defaulting to 'full'."""
        view = self.store.get(view_id)
        if not view:
            return "full"
        return (view.metadata
                .get("panel", {})
                .get("size_hint", "full"))

    def to_dict(self) -> dict[str, Any]:
        return {
            "views": self.store.to_dict(), "registry": self.registry.to_dict(),
            "push_channel": self.push_channel.to_dict(),
            "adapters": [a["type"] for a in self.list_adapters()],
            "default_adapter": self._default_adapter,
        }
