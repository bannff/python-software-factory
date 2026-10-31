"""Inline-HTML render adapter (A2UI → HTML envelope).

Renders A2UI views and components into a self-contained HTML envelope
suitable for clients that expect inline HTML output. Internal name; not
related to the upstream `@mcp-ui/client` SDK.

History: previously named ``McpUiAdapter`` and lived in
``mcpui_adapter.py``. Renamed under bd:python-factory-kxpnf and re-run
under bd:python-factory-lo1g9.0 to free the ``mcp-ui`` namespace for
real `@mcp-ui` SDK adoption (carrier #5, EPIC bd:python-factory-lo1g9).

Same HTML output, same `view_manager.py` wiring — pure rename + content_type
relabel.

* file: ``mcpui_adapter.py → inline_html_adapter.py``
* class: ``McpUiAdapter → InlineHtmlRenderAdapter``
* ``adapter_type``: ``"mcp-ui" → "inline-html"``
* ``content_type``: ``application/vnd.mcp-ui+json →``
  ``application/vnd.factory.inline-html+json``
"""

from enum import Enum

from ..models import ComponentType, UIComponent, UIView
from .base import RenderAdapter, RenderResult
from . import html_renderers as hr


class UIResourceType(str, Enum):
    """Inline HTML resource types (legacy enum kept for back-compat)."""

    INLINE_HTML = "inline_html"
    EXTERNAL_URL = "external_url"
    REMOTE_DOM = "remote_dom"


class InlineHtmlRenderAdapter(RenderAdapter):
    """Renders A2UI views/components into an inline HTML envelope.

    The adapter wraps the rendered HTML in a small JSON envelope so the
    client can distinguish content type and route it correctly. Internal
    naming only — not related to the `@mcp-ui` SDK.
    """

    def __init__(self, resource_type: UIResourceType = UIResourceType.INLINE_HTML) -> None:
        self._resource_type = resource_type

    @property
    def adapter_type(self) -> str:
        return "inline-html"

    @property
    def content_type(self) -> str:
        return "application/vnd.factory.inline-html+json"

    def render_view(self, view: UIView) -> RenderResult:
        """Render view as inline-HTML envelope."""
        html = self._view_to_html(view)

        ui_resource = {
            "type": self._resource_type.value,
            "content": html,
            "metadata": {
                "view_id": view.id,
                "view_name": view.name,
                "version": view.version,
            },
        }

        return RenderResult(
            adapter_type=self.adapter_type,
            content=ui_resource,
            content_type=self.content_type,
            metadata={
                "resource_type": self._resource_type.value,
                "component_count": len(view.components),
            },
        )

    def render_component(self, component: UIComponent) -> RenderResult:
        """Render component as inline-HTML envelope."""
        html = self._component_to_html(component)

        ui_resource = {
            "type": self._resource_type.value,
            "content": html,
            "metadata": {
                "component_id": component.id,
                "component_type": component.component_type.value,
            },
        }

        return RenderResult(
            adapter_type=self.adapter_type,
            content=ui_resource,
            content_type=self.content_type,
        )

    def _view_to_html(self, view: UIView) -> str:
        """Convert view to HTML string."""
        components_html = "\n".join(self._component_to_html(c) for c in view.components)
        styles = hr.generate_view_styles(view)

        return f"""<div class="mcp-ui-view" data-view-id="{view.id}">
  <style>{styles}</style>
  <div class="view-header">
    <h2>{view.name}</h2>
  </div>
  <div class="view-content" style="{hr.layout_to_css(view.layout)}">
    {components_html}
  </div>
</div>"""

    def _component_to_html(self, component: UIComponent) -> str:
        """Convert component to HTML string."""
        renderer = self._get_component_renderer(component.component_type)
        # Card needs special handling for recursive children
        if component.component_type == ComponentType.CARD:
            return hr.render_card(component, self._component_to_html)
        return renderer(component)

    def _get_component_renderer(self, component_type: ComponentType):
        """Get the HTML renderer for a component type."""
        renderers = {
            ComponentType.TEXT: hr.render_text,
            ComponentType.CHART: hr.render_chart,
            ComponentType.TABLE: hr.render_table,
            ComponentType.METRIC: hr.render_metric,
            ComponentType.CARD: hr.render_card,
            ComponentType.ALERT: hr.render_alert,
            ComponentType.PROGRESS: hr.render_progress,
            ComponentType.FORM: hr.render_form,
            ComponentType.BUTTON: hr.render_button,
            ComponentType.IMAGE: hr.render_image,
            ComponentType.LIST: hr.render_list,
        }
        return renderers.get(component_type, hr.render_custom)
