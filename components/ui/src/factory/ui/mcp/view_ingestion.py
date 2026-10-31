"""MCP tools that hydrate and render brick-declared view data."""
from __future__ import annotations

import logging
from typing import Any, Callable, TYPE_CHECKING

from factory.mcp_utils.interface import ToolResult, fail, operational

from .view_ingestion_dtos import (
    RegisterBrickViewsInput, RegisterBrickViewsOutput, RenderViewInput,
    RenderViewOutput,
)

if TYPE_CHECKING:
    from ..runtime.runtime import UIRuntime

logger = logging.getLogger(__name__)


def register(mcp: Any, get_runtime: Callable[[], "UIRuntime"]) -> None:
    """Register brick-view ingestion and rendering tools."""

    @mcp.tool()
    @operational(input_model=RegisterBrickViewsInput, output_model=RegisterBrickViewsOutput)
    def ui_register_brick_views(
        views: list[dict[str, Any]],
    ) -> ToolResult[RegisterBrickViewsOutput]:
        """Hydrate brick-declared views into the ViewManager store."""
        from ..runtime.a2ui import normalize_view_actions
        from ..runtime.a2ui.action_resolve import build_tool_resolver
        from ..runtime.models import ComponentType, UIComponent, UIView

        runtime = get_runtime()
        if not runtime.view_manager:
            return fail("Runtime not initialized")
        views = normalize_view_actions(views, resolver=build_tool_resolver())

        def _hydrate(cdef: dict[str, Any]) -> UIComponent:
            return UIComponent(
                id=cdef.get("id", ""),
                component_type=ComponentType(cdef.get("type", "text")),
                props=cdef.get("props", {}), styles=cdef.get("styles", {}),
                children=[_hydrate(child) for child in cdef.get("children", [])],
            )

        registered: list[str] = []
        errors: list[dict[str, str]] = []
        for vdef in views:
            try:
                view = UIView(
                    id=vdef["id"], name=vdef.get("name", vdef["id"]),
                    components=[_hydrate(c) for c in vdef.get("components", [])],
                    layout=vdef.get("layout", {}), metadata=vdef.get("metadata", {}),
                )
                runtime.view_manager.store.save(view)
                registered.append(vdef["id"])
            except Exception as exc:
                errors.append({"id": vdef.get("id", "?"), "error": str(exc)})
                logger.warning("Failed to register view %s: %s", vdef.get("id"), exc)
        return RegisterBrickViewsOutput(
            registered=registered, count=len(registered), errors=errors,
        )

    @mcp.tool()
    @operational(input_model=RenderViewInput, output_model=RenderViewOutput)
    def ui_render_view(
        view_id: str, adapter: str = "htmx",
    ) -> ToolResult[RenderViewOutput]:
        """Render one stored view with the requested adapter."""
        runtime = get_runtime()
        if not runtime.view_manager:
            return fail("Runtime not initialized")
        result = runtime.view_manager.render(view_id, adapter_type=adapter)
        if not result:
            return fail(f"View not found: {view_id}")
        return RenderViewOutput(
            view_id=view_id, adapter=result.adapter_type,
            content_type=result.content_type, content=result.content,
            metadata=result.metadata,
        )
