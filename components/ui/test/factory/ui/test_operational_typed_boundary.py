"""Focused typed-boundary tests for UI operational MCP tools."""
from __future__ import annotations

from typing import Any, get_type_hints

import pytest

from factory.mcp_utils.interface import ToolResult
from factory.mcp_utils.runtime.schema_migration import SchemaMigrationError
from factory.ui.mcp.operational import register
from factory.ui.mcp.operational_dtos import (
    ConnectClientInput, ConnectClientOutput, DisconnectClientInput,
    DisconnectClientOutput, GetViewInput, ListViewsInput, ListViewsOutput,
    PushChannelStatusInput, PushChannelStatusOutput, RenderedViewOutput,
    SubscribeInput, SubscribeOutput, ViewHistoryInput, ViewHistoryOutput,
)
from factory.ui.runtime.envelope import ContextEnvelope
from factory.ui.runtime.runtime import UIRuntime


class _Harness:
    def __init__(self) -> None:
        self.tools: dict[str, Any] = {}

    def tool(self):
        def decorate(fn: Any) -> Any:
            self.tools[fn.__name__] = fn
            return fn
        return decorate


def _tools(runtime: UIRuntime) -> dict[str, Any]:
    harness = _Harness()
    register(harness, lambda: runtime, ContextEnvelope.from_dict)
    return harness.tools


_EXPECTED = {
    "ui_list_views": (ListViewsInput, ListViewsOutput),
    "ui_get_view": (GetViewInput, RenderedViewOutput),
    "ui_get_push_channel_status": (PushChannelStatusInput, PushChannelStatusOutput),
    "ui_get_view_history": (ViewHistoryInput, ViewHistoryOutput),
    "ui_connect_client": (ConnectClientInput, ConnectClientOutput),
    "ui_disconnect_client": (DisconnectClientInput, DisconnectClientOutput),
    "ui_subscribe": (SubscribeInput, SubscribeOutput),
}


def test_all_operational_tools_have_strict_typed_boundaries() -> None:
    tools = _tools(UIRuntime())

    assert set(tools) == set(_EXPECTED)
    for name, (input_model, output_model) in _EXPECTED.items():
        tool = tools[name]
        assert tool._mcp_input_model is input_model
        assert tool._mcp_output_model is output_model
        assert input_model.model_config["extra"] == "forbid"
        assert output_model.model_config["extra"] == "forbid"
        assert get_type_hints(tool)["return"] == ToolResult[output_model]


def test_nested_envelope_is_strict() -> None:
    tool = _tools(UIRuntime())["ui_list_views"]

    with pytest.raises(SchemaMigrationError):
        tool(envelope={"unexpected": "field"})


def test_failure_is_an_outer_tool_result_envelope() -> None:
    result = _tools(UIRuntime())["ui_get_view"](view_id="missing")

    assert result.ok is False
    assert result.data is None
    assert result.error == "Runtime not initialized"


def test_domain_negative_subscription_remains_success_data() -> None:
    runtime = UIRuntime()
    runtime.initialize()
    result = _tools(runtime)["ui_subscribe"](client_id="missing", view_id="view")

    assert result.ok is True
    assert result.data == SubscribeOutput(
        subscribed=False, client_id="missing", view_id="view",
        request_id=result.data.request_id,
    )
