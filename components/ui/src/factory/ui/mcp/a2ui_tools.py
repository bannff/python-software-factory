"""A2UI Protocol MCP tools for agent-generated UI."""
from __future__ import annotations

from typing import Any, Callable, TYPE_CHECKING

from factory.mcp_utils.interface import ToolResult, deterministic, fail, operational

from .typed_dtos import (
    A2UIComponentCatalogOutput,
    A2UIPayloadInput,
    A2UIRenderOutput,
    A2UIToViewInput,
    A2UIValidationOutput,
    A2UIViewOutput,
    EmptyInput,
    RenderA2UIInput,
    ViewA2UIOutput,
    ViewIdInput,
)

if TYPE_CHECKING:
    from ..runtime.runtime import UIRuntime


def register(mcp: Any, get_runtime: Callable[[], "UIRuntime"]) -> None:
    """Register A2UI tools."""

    @mcp.tool()
    @deterministic(input_model=EmptyInput, output_model=A2UIComponentCatalogOutput)
    def ui_get_a2ui_component_catalog() -> ToolResult[A2UIComponentCatalogOutput]:
        """Get supported A2UI component types."""
        from ..runtime.a2ui import get_supported_components

        return A2UIComponentCatalogOutput(
            components=get_supported_components(), version="0.8", protocol="a2ui", reference="https://a2ui.org/"
        )

    @mcp.tool()
    @deterministic(input_model=A2UIPayloadInput, output_model=A2UIValidationOutput)
    def ui_validate_a2ui(payload: dict[str, Any]) -> ToolResult[A2UIValidationOutput]:
        """Validate an A2UI payload before rendering."""
        from ..runtime.a2ui import validate_a2ui

        errors = validate_a2ui(payload)
        return A2UIValidationOutput(
            valid=not errors,
            errors=[{"path": error.path, "message": error.message, "componentId": error.component_id} for error in errors],
            component_count=len(payload.get("components", [])),
        )

    @mcp.tool()
    @operational(input_model=RenderA2UIInput, output_model=A2UIRenderOutput)
    def ui_render_a2ui(
        payload: dict[str, Any],
        backend: str = "htmx",
        view_name: str = "A2UI View",
    ) -> ToolResult[A2UIRenderOutput]:
        """Render an A2UI payload with the specified backend."""
        from ..runtime.adapters import create_a2ui_adapter

        result = create_a2ui_adapter(backend=backend).render_a2ui(payload)  # type: ignore[arg-type]
        return A2UIRenderOutput(content=result.content, content_type=result.content_type, adapter=result.adapter_type, metadata=result.metadata)

    @mcp.tool()
    @operational(input_model=A2UIToViewInput, output_model=A2UIViewOutput)
    def ui_a2ui_to_view(
        payload: dict[str, Any],
        view_id: str | None = None,
        view_name: str = "A2UI View",
        save: bool = False,
    ) -> ToolResult[A2UIViewOutput]:
        """Convert an A2UI payload to a native UIView."""
        from ..runtime.a2ui import a2ui_to_ui_view

        view = a2ui_to_ui_view(payload, view_id, view_name)
        runtime = get_runtime()
        if save and runtime.view_manager:
            runtime.view_manager.save_view(view)
        return A2UIViewOutput(view=view.to_dict(), saved=save, component_count=len(view.components))

    @mcp.tool()
    @deterministic(input_model=ViewIdInput, output_model=ViewA2UIOutput)
    def ui_view_to_a2ui(view_id: str) -> ToolResult[ViewA2UIOutput]:
        """Convert a stored UIView back to A2UI format."""
        from ..runtime.a2ui import ui_view_to_a2ui

        runtime = get_runtime()
        if not runtime.view_manager:
            return fail("View manager not initialized")
        view = runtime.view_manager.get_view(view_id)
        if not view:
            return fail(f"View not found: {view_id}")
        return ViewA2UIOutput(**ui_view_to_a2ui(view))
