"""React/shadcn adapter for SPA consumption.

Renders views as JSON schemas optimized for React frontends using
shadcn/ui components. The output includes component mappings and
theme tokens that React apps can interpret.

This adapter is ideal for:
- User-facing polished UIs
- Complex interactive dashboards
- SPAs with rich animations (Magic UI, Aceternity)
"""

from typing import Any

from ..models import UIComponent, UIView
from .base import RenderAdapter, RenderResult
from .react_transforms import (
    SHADCN_COMPONENT_MAP,
    transform_props,
    transform_layout,
    get_animation_hint,
    get_theme_tokens,
)


class ReactAdapter(RenderAdapter):
    """Renders views as JSON for React/shadcn consumption.

    Output is a JSON structure that React apps can interpret to render
    shadcn/ui components. Includes:
    - Component tree with shadcn component names
    - Props mapped to shadcn conventions
    - Theme tokens (CSS variables)
    - Animation hints for Magic UI/Aceternity
    """

    def __init__(
        self,
        theme: str = "default",
        include_animations: bool = True,
        animation_library: str = "magic-ui",
    ) -> None:
        self._theme = theme
        self._include_animations = include_animations
        self._animation_library = animation_library

    @property
    def adapter_type(self) -> str:
        return "react"

    @property
    def content_type(self) -> str:
        return "application/json"

    def render_view(self, view: UIView) -> RenderResult:
        """Render view as React-consumable JSON."""
        components = [self._transform_component(c) for c in view.components]

        schema = {
            "type": "view",
            "id": view.id,
            "name": view.name,
            "layout": transform_layout(view.layout),
            "components": components,
            "theme": get_theme_tokens(self._theme),
            "metadata": {
                "version": view.version,
                "adapter": self.adapter_type,
                "animation_library": self._animation_library if self._include_animations else None,
            },
        }

        return RenderResult(
            adapter_type=self.adapter_type,
            content=schema,
            content_type=self.content_type,
            metadata={
                "theme": self._theme,
                "component_count": len(view.components),
                "animations_enabled": self._include_animations,
            },
        )

    def render_component(self, component: UIComponent) -> RenderResult:
        """Render single component as React JSON."""
        schema = self._transform_component(component)
        return RenderResult(
            adapter_type=self.adapter_type,
            content=schema,
            content_type=self.content_type,
        )

    def supports_streaming(self) -> bool:
        return True  # Can stream JSON patches

    def _transform_component(self, c: UIComponent) -> dict[str, Any]:
        """Transform UIComponent to React/shadcn schema."""
        shadcn_type = SHADCN_COMPONENT_MAP.get(c.component_type, "Custom")
        props = transform_props(c.component_type, c.props)
        children = [self._transform_component(ch) for ch in c.children]

        schema: dict[str, Any] = {
            "id": c.id,
            "component": shadcn_type,
            "originalType": c.component_type.value,
            "props": props,
        }

        if children:
            schema["children"] = children

        if self._include_animations:
            hint = get_animation_hint(c.component_type, self._animation_library)
            if hint:
                schema["animation"] = hint

        return schema
