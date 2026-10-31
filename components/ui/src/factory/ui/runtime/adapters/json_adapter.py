"""JSON adapter for generic frontend consumption."""

from ..models import UIComponent, UIView
from .base import RenderAdapter, RenderResult


class JsonAdapter(RenderAdapter):
    """Renders views as JSON for consumption by any frontend.

    This is the default adapter - it outputs a JSON structure
    that frontends can interpret and render however they want.
    """

    @property
    def adapter_type(self) -> str:
        return "json"

    @property
    def content_type(self) -> str:
        return "application/json"

    def render_view(self, view: UIView) -> RenderResult:
        """Render view as JSON."""
        return RenderResult(
            adapter_type=self.adapter_type,
            content=view.to_dict(),
            content_type=self.content_type,
            metadata={"component_count": len(view.components)},
        )

    def render_component(self, component: UIComponent) -> RenderResult:
        """Render component as JSON."""
        return RenderResult(
            adapter_type=self.adapter_type,
            content=component.to_dict(),
            content_type=self.content_type,
        )

    def supports_streaming(self) -> bool:
        return True
