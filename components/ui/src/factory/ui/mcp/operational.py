"""Typed operational MCP tools for the UI module."""
from __future__ import annotations

from typing import Any, Callable, TYPE_CHECKING

from factory.mcp_utils.interface import ToolResult, operational

from .operational_dtos import (
    ConnectClientInput, ConnectClientOutput, DisconnectClientInput,
    DisconnectClientOutput, GetViewInput, ListViewsInput, ListViewsOutput,
    PushChannelStatusInput, PushChannelStatusOutput, RenderedViewOutput,
    SubscribeInput, SubscribeOutput, ViewHistoryInput, ViewHistoryOutput,
)

if TYPE_CHECKING:
    from ..runtime.envelope import ContextEnvelope
    from ..runtime.runtime import UIRuntime


def register(
    mcp: Any,
    get_runtime: Callable[[], "UIRuntime"],
    parse_envelope: Callable[[dict[str, Any] | None], "ContextEnvelope"],
) -> None:
    """Register typed operational UI tools."""

    @mcp.tool()
    @operational(input_model=ListViewsInput, output_model=ListViewsOutput)
    def ui_list_views(envelope: dict[str, Any] | None = None) -> ToolResult[ListViewsOutput]:
        """List all available views."""
        ctx = parse_envelope(envelope)
        runtime = get_runtime()
        if not runtime.view_manager:
            return ToolResult(ok=False, data=None, error="Runtime not initialized")
        views = runtime.view_manager.list_views()
        return ListViewsOutput(views=[{
            "id": view.id, "name": view.name, "component_count": len(view.components),
            "version": view.version, "updated_at": view.updated_at.isoformat(),
        } for view in views], total=len(views), request_id=ctx.request_id)

    @mcp.tool()
    @operational(input_model=GetViewInput, output_model=RenderedViewOutput)
    def ui_get_view(view_id: str, adapter: str = "json", route: str | None = None,
                    envelope: dict[str, Any] | None = None) -> ToolResult[RenderedViewOutput]:
        """Get a view by ID, optionally rendered through an adapter."""
        ctx = parse_envelope(envelope)
        runtime = get_runtime()
        if not runtime.view_manager:
            return ToolResult(ok=False, data=None, error="Runtime not initialized")
        result = runtime.view_manager.render(view_id, adapter_type=adapter, route=route)
        if not result:
            return ToolResult(ok=False, data=None, error=f"View not found: {view_id}")
        return RenderedViewOutput(**result.to_dict(), request_id=ctx.request_id)

    @mcp.tool()
    @operational(input_model=PushChannelStatusInput, output_model=PushChannelStatusOutput)
    def ui_get_push_channel_status(envelope: dict[str, Any] | None = None) -> ToolResult[PushChannelStatusOutput]:
        """Get the status of the push channel."""
        ctx = parse_envelope(envelope)
        runtime = get_runtime()
        if not runtime.view_manager:
            return ToolResult(ok=False, data=None, error="Runtime not initialized")
        return PushChannelStatusOutput(**runtime.view_manager.push_channel.to_dict(), request_id=ctx.request_id)

    @mcp.tool()
    @operational(input_model=ViewHistoryInput, output_model=ViewHistoryOutput)
    def ui_get_view_history(view_id: str | None = None, limit: int = 50,
                            envelope: dict[str, Any] | None = None) -> ToolResult[ViewHistoryOutput]:
        """Get update history for views."""
        ctx = parse_envelope(envelope)
        runtime = get_runtime()
        if not runtime.view_manager:
            return ToolResult(ok=False, data=None, error="Runtime not initialized")
        history = runtime.view_manager.store.get_history(view_id=view_id, limit=limit)
        return ViewHistoryOutput(updates=[update.to_dict() for update in history], count=len(history), request_id=ctx.request_id)

    @mcp.tool()
    @operational(input_model=ConnectClientInput, output_model=ConnectClientOutput)
    def ui_connect_client(client_id: str, subscribe_to: list[str] | None = None,
                          envelope: dict[str, Any] | None = None) -> ToolResult[ConnectClientOutput]:
        """Register a client connection for receiving updates."""
        ctx = parse_envelope(envelope)
        runtime = get_runtime()
        if not runtime.view_manager:
            return ToolResult(ok=False, data=None, error="Runtime not initialized")
        connection = runtime.view_manager.push_channel.connect(client_id)
        for view_id in subscribe_to or []:
            runtime.view_manager.push_channel.subscribe(client_id, view_id)
        return ConnectClientOutput(connected=True, client_id=client_id,
                                   subscribed_to=list(connection.subscribed_views), request_id=ctx.request_id)

    @mcp.tool()
    @operational(input_model=DisconnectClientInput, output_model=DisconnectClientOutput)
    def ui_disconnect_client(client_id: str, envelope: dict[str, Any] | None = None) -> ToolResult[DisconnectClientOutput]:
        """Disconnect a client."""
        ctx = parse_envelope(envelope)
        runtime = get_runtime()
        if not runtime.view_manager:
            return ToolResult(ok=False, data=None, error="Runtime not initialized")
        return DisconnectClientOutput(disconnected=runtime.view_manager.push_channel.disconnect(client_id),
                                      client_id=client_id, request_id=ctx.request_id)

    @mcp.tool()
    @operational(input_model=SubscribeInput, output_model=SubscribeOutput)
    def ui_subscribe(client_id: str, view_id: str,
                     envelope: dict[str, Any] | None = None) -> ToolResult[SubscribeOutput]:
        """Subscribe a client to view updates."""
        ctx = parse_envelope(envelope)
        runtime = get_runtime()
        if not runtime.view_manager:
            return ToolResult(ok=False, data=None, error="Runtime not initialized")
        return SubscribeOutput(subscribed=runtime.view_manager.push_channel.subscribe(client_id, view_id),
                               client_id=client_id, view_id=view_id, request_id=ctx.request_id)
