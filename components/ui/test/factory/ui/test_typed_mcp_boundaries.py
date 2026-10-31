"""Typed-boundary proof for UI deterministic and A2UI MCP tools."""
from __future__ import annotations

import asyncio
from typing import get_type_hints

import pytest
from pydantic import BaseModel

from factory.mcp_utils.interface import ToolResult
from factory.mcp_utils.runtime.schema_migration import SchemaMigrationError
from factory.ui.server import create_mcp_server


TOOLS = {
    "ui_get_capabilities", "ui_health_check", "ui_describe_config_schema",
    "ui_get_view_registry", "ui_get_component_registry", "ui_list_adapters",
    "ui_get_theme_info", "ui_get_a2ui_component_catalog", "ui_validate_a2ui",
    "ui_render_a2ui", "ui_a2ui_to_view", "ui_view_to_a2ui",
}


def _tool(server, name):
    return asyncio.run(server.get_tool(name))


@pytest.mark.asyncio
async def test_selected_ui_families_have_strict_typed_boundaries() -> None:
    tools = await create_mcp_server().list_tools()
    selected = [tool for tool in tools if tool.name in TOOLS]
    assert {tool.name for tool in selected} == TOOLS
    for tool in selected:
        function = tool.fn
        input_model = function._mcp_input_model
        output_model = function._mcp_output_model
        for model in (input_model, output_model):
            assert issubclass(model, BaseModel)
            assert model.__module__.startswith("factory.ui.mcp.")
            assert model.model_config["extra"] == "forbid"
        result_type = get_type_hints(function)["return"]
        assert result_type.__pydantic_generic_metadata__["origin"] is ToolResult
        assert result_type.__pydantic_generic_metadata__["args"] == (output_model,)


def test_a2ui_validation_false_is_success_data_and_unknown_fields_fail() -> None:
    server = create_mcp_server()
    validation = _tool(server, "ui_validate_a2ui").fn(payload={})
    assert validation.ok is True
    assert validation.data.valid is False
    with pytest.raises(SchemaMigrationError):
        _tool(server, "ui_get_theme_info").fn(unknown=True)


def test_missing_view_is_a_failed_envelope() -> None:
    result = _tool(create_mcp_server(), "ui_view_to_a2ui").fn(view_id="missing")
    assert result.ok is False
    assert result.data is None
    assert result.error == "View not found: missing"
