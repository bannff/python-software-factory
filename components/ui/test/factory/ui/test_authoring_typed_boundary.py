"""Focused strict typed-boundary tests for UI authoring tools."""

from __future__ import annotations

from typing import get_type_hints

import pytest
from pydantic import BaseModel, ValidationError

from factory.mcp_utils.interface import ToolResult
from factory.ui.server import create_mcp_server
from factory.ui.runtime.runtime import UIRuntime


AUTHORING_TOOLS = {
    "ui_authoring_get_status",
    "ui_create_view",
    "ui_delete_view",
    "ui_add_component",
    "ui_update_component",
    "ui_remove_component",
    "ui_push_view",
    "ui_create_dashboard",
}


def _server(config_dir: str):
    runtime = UIRuntime(config_dir)
    runtime.initialize()
    return create_mcp_server(runtime)


@pytest.mark.asyncio
async def test_authoring_family_uses_strict_same_brick_dtos(config_dir: str) -> None:
    tools = await _server(config_dir).list_tools()
    authoring_tools = [tool for tool in tools if tool.name in AUTHORING_TOOLS]

    assert {tool.name for tool in authoring_tools} == AUTHORING_TOOLS
    for tool in authoring_tools:
        function = tool.fn
        input_model = function._mcp_input_model
        output_model = function._mcp_output_model
        assert function._mcp_category == "authoring"
        for model in (input_model, output_model):
            assert issubclass(model, BaseModel)
            assert model.__module__ == "factory.ui.mcp.authoring_dtos"
            assert model.model_config["extra"] == "forbid"
        metadata = get_type_hints(function)["return"].__pydantic_generic_metadata__
        assert metadata["origin"] is ToolResult
        assert metadata["args"] == (output_model,)
        with pytest.raises(ValidationError):
            input_model.model_validate({"unexpected": True})


@pytest.mark.asyncio
async def test_authoring_errors_fail_but_normal_negative_results_are_data(
    config_dir: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    disabled = _server(config_dir)
    create = await disabled.get_tool("ui_create_view")
    blocked = create.fn(name="blocked")
    assert not blocked.ok
    assert blocked.data is None
    assert blocked.error == "Authoring tools disabled"

    monkeypatch.setenv("AUTHORING_ENABLED", "true")
    enabled = _server(config_dir)
    create = await enabled.get_tool("ui_create_view")
    view = create.fn(name="dashboard", view_id="view-1")
    assert view.ok and view.data.view["layout"] == {"type": "flex"}

    delete = await enabled.get_tool("ui_delete_view")
    missing = delete.fn(view_id="missing")
    assert missing.ok and missing.data.deleted is False

    remove = await enabled.get_tool("ui_remove_component")
    absent_component = await remove.fn(view_id="view-1", component_id="missing")
    assert absent_component.ok and absent_component.data.removed is False

    push = await enabled.get_tool("ui_push_view")
    absent_view = await push.fn(view_id="missing")
    assert absent_view.ok and absent_view.data.recipients == 0


@pytest.mark.asyncio
async def test_dashboard_authoring_preserves_flat_defaults(
    config_dir: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("AUTHORING_ENABLED", "true")
    dashboard = await _server(config_dir).get_tool("ui_create_dashboard")

    result = await dashboard.fn(name="ops", metrics=[{"label": "Open"}])

    assert result.ok
    assert result.data.created is True
