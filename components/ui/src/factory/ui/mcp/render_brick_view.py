"""Render a brick-declared view as flat A2UI components for inline chat."""
from __future__ import annotations

from typing import Any, Callable, TYPE_CHECKING

from factory.mcp_utils.interface import ToolResult, fail, operational

from .render_brick_view_dtos import RenderBrickViewInput, RenderBrickViewOutput

if TYPE_CHECKING:
    from ..runtime.runtime import UIRuntime


def register(mcp: Any, get_runtime: Callable[[], "UIRuntime"]) -> None:
    """Register the inline brick-view renderer."""
    del get_runtime

    @mcp.tool()
    @operational(input_model=RenderBrickViewInput, output_model=RenderBrickViewOutput)
    def ui_render_brick_view(
        brick_name: str, view_id: str | None = None,
    ) -> ToolResult[RenderBrickViewOutput]:
        """Return the ``{components, name}`` A2UI carrier for one brick view."""
        from factory.mcp_utils.interface import get_service
        from ..runtime.a2ui import ui_view_to_a2ui
        from ..runtime.models import ComponentType, UIComponent, UIView

        invoker = get_service("tool_invoker")
        if invoker is None:
            return fail("tool_invoker not registered (gateway not initialized)")
        tool_name = f"{brick_name}_get_views"
        try:
            views = invoker(tool_name)
        except Exception as exc:
            return fail(f"Failed to invoke {tool_name}: {exc}")
        if isinstance(views, dict) and "error" in views:
            return fail(f"Brick not found: {brick_name}")
        if not isinstance(views, list) or not views:
            return fail(f"Brick {brick_name} declares no views")

        chosen: dict[str, Any] | None = None
        if view_id is None:
            chosen = views[0] if isinstance(views[0], dict) else None
        else:
            chosen = next(
                (view for view in views if isinstance(view, dict) and view.get("id") == view_id),
                None,
            )
        if chosen is None:
            return fail(
                f"View not found: {view_id}" if view_id else
                f"Brick {brick_name} declares no views",
            )

        def _hydrate(cdef: dict[str, Any]) -> UIComponent:
            children = [_hydrate(child) for child in cdef.get("children", [])]
            try:
                component_type = ComponentType(cdef.get("type", "text"))
            except ValueError:
                component_type = ComponentType.CUSTOM
            props = dict(cdef.get("props", {}))
            props.setdefault("_a2ui_type", cdef.get("type", "text"))
            return UIComponent(
                id=cdef.get("id", ""), component_type=component_type,
                props=props, styles=cdef.get("styles", {}), children=children,
            )

        try:
            view = UIView(
                id=chosen.get("id", ""), name=chosen.get("name", chosen.get("id", "")),
                components=[_hydrate(c) for c in chosen.get("components", [])],
                layout=chosen.get("layout", {}), metadata=chosen.get("metadata", {}),
            )
            payload = ui_view_to_a2ui(view)
        except Exception as exc:
            return fail(f"Failed to render view: {exc}")
        return RenderBrickViewOutput(
            components=payload.get("components", []), name=view.name,
        )
