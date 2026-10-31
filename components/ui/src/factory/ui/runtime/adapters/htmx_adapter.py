"""HTMX adapter for server-rendered hypermedia UI.

Renders views as HTML with HTMX attributes for dynamic updates,
Alpine.js for client-side interactivity, and DaisyUI for styling.

This adapter is ideal for:
- Agent-facing dashboards (fast, simple, low JS overhead)
- Server-rendered applications
- Progressive enhancement patterns
"""

from ..models import ComponentType, UIComponent, UIView
from .base import RenderAdapter, RenderResult
from . import htmx_renderers as hr
from . import htmx_renderers_ext as hx
from .htmx_renderers_page import render_page_skeleton
from .htmx_renderers_chart import render_chart_js
from .htmx_renderers_action_pane import render_action_pane
from .htmx_renderers_interactive import (
    render_code_block, render_timeline, render_stat_grid,
)
from .htmx_renderers_tree import render_tree_view, render_live_feed
from .htmx_renderers_table import render_table
from .htmx_renderers_composed import render_composed_page
from .htmx_renderers_chat import render_chat


class HTMXAdapter(RenderAdapter):
    """Renders views as HTMX-enhanced HTML with DaisyUI styling.

    Output includes:
    - DaisyUI CSS classes for styling
    - HTMX attributes for server-driven updates
    - Alpine.js x-data for client-side state
    """

    def __init__(
        self,
        hx_boost: bool = True,
        include_alpine: bool = True,
    ) -> None:
        self._hx_boost = hx_boost
        self._include_alpine = include_alpine

    @property
    def adapter_type(self) -> str:
        return "htmx"

    @property
    def content_type(self) -> str:
        return "text/html"

    def render_view(self, view: UIView) -> RenderResult:
        """Render view as HTMX-enhanced HTML."""
        components_html = "\n".join(
            self._render_component(c) for c in view.components
        )
        layout_class = hr.layout_to_class(view.layout)
        hx_attrs = 'hx-boost="true"' if self._hx_boost else ""

        html = f'''<div class="p-4" {hx_attrs}
     data-view-id="{view.id}" id="view-{view.id}">
  <div class="{layout_class}">
    {components_html}
  </div>
</div>'''

        return RenderResult(
            adapter_type=self.adapter_type,
            content=html,
            content_type=self.content_type,
            metadata={
                "component_count": len(view.components),
                "hx_boost": self._hx_boost,
            },
        )

    def render_component(self, component: UIComponent) -> RenderResult:
        """Render single component as HTMX HTML."""
        html = self._render_component(component)
        return RenderResult(
            adapter_type=self.adapter_type,
            content=html,
            content_type=self.content_type,
        )

    def supports_streaming(self) -> bool:
        return True  # HTMX supports SSE/WebSocket streaming

    def _render_component(self, c: UIComponent) -> str:
        """Dispatch to component-specific renderer."""
        renderers = {
            ComponentType.TEXT: hr.render_text,
            ComponentType.BUTTON: hr.render_button,
            ComponentType.TABLE: render_table,
            ComponentType.METRIC: hr.render_metric,
            ComponentType.ALERT: hr.render_alert,
            ComponentType.PROGRESS: hr.render_progress,
            ComponentType.FORM: hr.render_form,
            ComponentType.LIST: hr.render_list,
            ComponentType.CHART: render_chart_js,
            ComponentType.IMAGE: hr.render_image,
            ComponentType.HERO: hx.render_hero,
            ComponentType.TABS: hx.render_tabs,
            ComponentType.BREADCRUMBS: hx.render_breadcrumbs,
            ComponentType.MODAL: hx.render_modal,
            ComponentType.TOAST: hx.render_toast,
            ComponentType.CODE_BLOCK: render_code_block,
            ComponentType.TIMELINE: render_timeline,
            ComponentType.STAT_GRID: render_stat_grid,
            ComponentType.TREE_VIEW: render_tree_view,
            ComponentType.LIVE_FEED: render_live_feed,
            ComponentType.CHAT: render_chat,
        }
        # Page skeleton needs recursive render for children
        if c.component_type == ComponentType.PAGE:
            return render_page_skeleton(c, self._render_component)
        # Composed page renders pre-resolved panel children
        if c.component_type == ComponentType.COMPOSED_PAGE:
            return render_composed_page(c, self._render_component)
        # Card needs special handling for recursive children
        if c.component_type == ComponentType.CARD:
            return hr.render_card(c, self._render_component)
        # Action pane is self-contained (no child components)
        if c.component_type == ComponentType.ACTION_PANE:
            return render_action_pane(c)
        renderer = renderers.get(c.component_type, hr.render_custom)
        return renderer(c)
