"""Whole-surface Pydantic v2 boundary proof for UI MCP tools."""
from __future__ import annotations

from typing import get_type_hints

import pytest
from pydantic import BaseModel

from factory.mcp_utils.interface import ToolResult
from factory.ui.server import create_mcp_server


TOOLS = {
    "ui_a2ui_to_view", "ui_add_component", "ui_authoring_get_status",
    "ui_connect_client", "ui_create_dashboard", "ui_create_view",
    "ui_delete_view", "ui_describe_config_schema", "ui_disconnect_client",
    "ui_dispatch_action", "ui_export_preferences", "ui_get_a2ui_component_catalog",
    "ui_get_capabilities", "ui_get_chat_preferences", "ui_get_component_registry",
    "ui_get_display_preferences", "ui_get_push_channel_status", "ui_get_theme_info", "ui_get_view",
    "ui_get_view_history", "ui_get_view_registry", "ui_health_check",
    "ui_import_preferences", "ui_list_adapters", "ui_list_views", "ui_paint_canvas", "ui_paint_chat",
    "ui_paint_uiresource", "ui_push_view", "ui_register_brick_views",
    "ui_remove_component", "ui_render_a2ui", "ui_render_brick_view",
    "ui_render_view", "ui_resolve_canvas", "ui_subscribe", "ui_update_chat_preferences",
    "ui_update_component", "ui_update_display_preferences", "ui_validate_a2ui", "ui_view_to_a2ui",
}


@pytest.mark.asyncio
async def test_fresh_server_exposes_exactly_forty_one_strict_typed_tools() -> None:
    tools = await create_mcp_server().list_tools()
    names = [tool.name for tool in tools]

    assert set(names) == TOOLS
    assert len(names) == len(set(names)) == 41
    assert not any(name.endswith("_v2") for name in names)

    for tool in tools:
        function = tool.fn
        input_model = function._mcp_input_model
        output_model = function._mcp_output_model
        assert function._mcp_category in {"deterministic", "operational", "authoring"}
        for model in (input_model, output_model):
            assert issubclass(model, BaseModel)
            assert model.__module__.startswith("factory.ui.mcp.")
            assert model.model_config["extra"] == "forbid"
        result_type = get_type_hints(function)["return"]
        metadata = result_type.__pydantic_generic_metadata__
        assert metadata["origin"] is ToolResult
        assert metadata["args"] == (output_model,)
