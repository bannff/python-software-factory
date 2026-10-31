"""MCP Tool registration for UI Module."""

from typing import Any

from . import (
    action_dispatch,
    deterministic,
    operational,
    authoring,
    authoring_dashboard,
    a2ui_tools,
    canvas_resolve,
    chat_preferences,
    display_preferences,
    preference_backup,
    view_ingestion,
    render_brick_view,
    paint_canvas,
    paint_chat,
    paint_uiresource,
)


def register(
    mcp: Any,
    get_runtime: Any,
    parse_envelope: Any,
    is_authoring_enabled: Any,
    chat_store: Any,
) -> None:
    """Register all UI tools with the MCP server."""
    deterministic.register(mcp, get_runtime)
    canvas_resolve.register(mcp, get_runtime)
    chat_preferences.register(mcp, chat_store)
    display_preferences.register(mcp, chat_store)
    preference_backup.register(mcp, chat_store)
    operational.register(mcp, get_runtime, parse_envelope)
    authoring.register(mcp, get_runtime, parse_envelope, is_authoring_enabled)
    authoring_dashboard.register(mcp, get_runtime, parse_envelope, is_authoring_enabled)
    a2ui_tools.register(mcp, get_runtime)
    view_ingestion.register(mcp, get_runtime)
    render_brick_view.register(mcp, get_runtime)
    action_dispatch.register(mcp, get_runtime)
    paint_canvas.register(mcp, get_runtime)
    paint_chat.register(mcp, get_runtime)
    paint_uiresource.register(mcp, get_runtime)
