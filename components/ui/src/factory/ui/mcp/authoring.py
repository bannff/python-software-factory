"""Security-gated authoring MCP tools for the UI module."""

from __future__ import annotations

from typing import Any, Callable, TYPE_CHECKING, cast

from factory.mcp_utils.interface import ToolResult, authoring, fail, ok

from .authoring_dtos import (
    AddComponentInput,
    AddComponentOutput,
    AuthoringStatusInput,
    AuthoringStatusOutput,
    CreateViewInput,
    CreateViewOutput,
    DeleteViewInput,
    DeleteViewOutput,
    PushViewInput,
    PushViewOutput,
    RemoveComponentInput,
    RemoveComponentOutput,
    UpdateComponentInput,
    UpdateComponentOutput,
)

if TYPE_CHECKING:
    from ..runtime.envelope import ContextEnvelope
    from ..runtime.runtime import UIRuntime


def _failed(error: str) -> ToolResult[Any]:
    """Return an explicitly typed failed authoring envelope."""
    return cast(ToolResult[Any], fail(error))


def register(
    mcp: Any,
    get_runtime: Callable[[], "UIRuntime"],
    parse_envelope: Callable[[dict[str, Any] | None], "ContextEnvelope"],
    is_authoring_enabled: Callable[[], bool],
) -> None:
    """Register security-gated typed UI authoring tools."""

    @mcp.tool()
    @authoring(input_model=AuthoringStatusInput, output_model=AuthoringStatusOutput)
    def ui_authoring_get_status() -> ToolResult[AuthoringStatusOutput]:
        """Get authoring tools status."""
        return ok(AuthoringStatusOutput.model_validate(get_runtime().get_authoring_status()))

    @mcp.tool()
    @authoring(input_model=CreateViewInput, output_model=CreateViewOutput)
    def ui_create_view(
        name: str,
        view_id: str | None = None,
        layout_type: str = "flex",
        layout_columns: int = 1,
        envelope: dict[str, Any] | None = None,
    ) -> ToolResult[CreateViewOutput]:
        """Create a new view."""
        ctx = parse_envelope(envelope)
        if not is_authoring_enabled():
            return _failed("Authoring tools disabled")
        layout = {"type": layout_type}
        if layout_type == "grid":
            layout["columns"] = layout_columns
        view = get_runtime().view_manager.create_view(name=name, view_id=view_id, layout=layout)
        return ok(CreateViewOutput(created=True, view=view.to_dict(), request_id=ctx.request_id))

    @mcp.tool()
    @authoring(input_model=DeleteViewInput, output_model=DeleteViewOutput)
    def ui_delete_view(
        view_id: str, envelope: dict[str, Any] | None = None
    ) -> ToolResult[DeleteViewOutput]:
        """Delete a view."""
        ctx = parse_envelope(envelope)
        if not is_authoring_enabled():
            return _failed("Authoring tools disabled")
        deleted = get_runtime().view_manager.delete_view(view_id)
        return ok(DeleteViewOutput(deleted=deleted, view_id=view_id, request_id=ctx.request_id))

    @mcp.tool()
    @authoring(input_model=AddComponentInput, output_model=AddComponentOutput)
    async def ui_add_component(
        view_id: str,
        component_type: str,
        props: dict[str, Any] | None = None,
        styles: dict[str, str] | None = None,
        component_id: str | None = None,
        position: int | None = None,
        envelope: dict[str, Any] | None = None,
    ) -> ToolResult[AddComponentOutput]:
        """Add a component to a view."""
        ctx = parse_envelope(envelope)
        if not is_authoring_enabled():
            return _failed("Authoring tools disabled")
        runtime = get_runtime()
        try:
            component = runtime.view_manager.create_component(
                component_type=component_type, props=props, styles=styles, component_id=component_id
            )
        except ValueError:
            return _failed(f"Invalid type: {component_type}")
        view = await runtime.view_manager.add_component(view_id, component, position)
        if not view:
            return _failed(f"View not found: {view_id}")
        return ok(AddComponentOutput(added=True, component=component.to_dict(), request_id=ctx.request_id))

    @mcp.tool()
    @authoring(input_model=UpdateComponentInput, output_model=UpdateComponentOutput)
    async def ui_update_component(
        view_id: str,
        component_id: str,
        props: dict[str, Any] | None = None,
        styles: dict[str, str] | None = None,
        envelope: dict[str, Any] | None = None,
    ) -> ToolResult[UpdateComponentOutput]:
        """Update a component's properties or styles."""
        ctx = parse_envelope(envelope)
        if not is_authoring_enabled():
            return _failed("Authoring tools disabled")
        component = await get_runtime().view_manager.update_component(
            view_id, component_id, props, styles
        )
        if not component:
            return _failed(f"Component not found: {component_id}")
        return ok(UpdateComponentOutput(updated=True, component=component.to_dict(), request_id=ctx.request_id))

    @mcp.tool()
    @authoring(input_model=RemoveComponentInput, output_model=RemoveComponentOutput)
    async def ui_remove_component(
        view_id: str, component_id: str, envelope: dict[str, Any] | None = None
    ) -> ToolResult[RemoveComponentOutput]:
        """Remove a component."""
        ctx = parse_envelope(envelope)
        if not is_authoring_enabled():
            return _failed("Authoring tools disabled")
        removed = await get_runtime().view_manager.remove_component(view_id, component_id)
        return ok(RemoveComponentOutput(removed=removed, component_id=component_id, request_id=ctx.request_id))

    @mcp.tool()
    @authoring(input_model=PushViewInput, output_model=PushViewOutput)
    async def ui_push_view(
        view_id: str, envelope: dict[str, Any] | None = None
    ) -> ToolResult[PushViewOutput]:
        """Push view state to clients."""
        ctx = parse_envelope(envelope)
        if not is_authoring_enabled():
            return _failed("Authoring tools disabled")
        recipients = await get_runtime().view_manager.push_view(view_id)
        return ok(PushViewOutput(
            pushed=True, view_id=view_id, recipients=recipients, request_id=ctx.request_id
        ))
