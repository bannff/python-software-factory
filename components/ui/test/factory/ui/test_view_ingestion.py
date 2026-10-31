"""Typed-boundary tests for brick view ingestion and rendering."""
from __future__ import annotations

from unittest.mock import MagicMock

from factory.mcp_utils.interface import ToolResult
from factory.ui.runtime.runtime import UIRuntime, reset_runtime


def _make_runtime() -> UIRuntime:
    reset_runtime()
    runtime = UIRuntime()
    runtime.initialize()
    return runtime


def _tools(runtime: UIRuntime):
    from factory.ui.mcp.view_ingestion import register

    mcp, tools = MagicMock(), {}

    def capture_tool():
        def decorate(fn):
            tools[fn.__name__] = fn
            return fn
        return decorate

    mcp.tool = capture_tool
    register(mcp, lambda: runtime)
    return tools


def _data(result: ToolResult):
    assert result.ok is True, result
    return result.data


def test_register_brick_views_hydrates_store():
    runtime = _make_runtime()
    result = _data(_tools(runtime)["ui_register_brick_views"](views=[{
        "id": "test-view", "name": "Test View",
        "components": [{"id": "c1", "type": "text", "props": {"content": "hello"}}],
        "layout": {"type": "grid", "columns": 2}, "metadata": {"nav_label": "Test"},
    }]))
    assert result.count == 1 and result.registered == ["test-view"]
    view = runtime.view_manager.get_view("test-view")
    assert view.name == "Test View"
    assert view.components[0].props["content"] == "hello"


def test_register_brick_views_replaces_existing():
    runtime, tools = _make_runtime(), None
    tools = _tools(runtime)
    tools["ui_register_brick_views"](views=[{"id": "v1", "name": "Original", "components": []}])
    _data(tools["ui_register_brick_views"](views=[{
        "id": "v1", "name": "Updated", "components": [{"id": "c1", "type": "text", "props": {}}],
    }]))
    assert runtime.view_manager.get_view("v1").name == "Updated"


def test_render_view_returns_typed_html_carrier():
    runtime, tools = _make_runtime(), None
    tools = _tools(runtime)
    tools["ui_register_brick_views"](views=[{
        "id": "render-test", "name": "Render Test",
        "components": [{"id": "t1", "type": "text", "props": {"content": "Hello World", "variant": "h2"}}],
        "layout": {"type": "flex"},
    }])
    result = _data(tools["ui_render_view"](view_id="render-test", adapter="htmx"))
    assert result.adapter == "htmx" and result.content_type == "text/html"
    assert "Hello World" in result.content


def test_render_view_missing_is_failed_outer_envelope():
    result = _tools(_make_runtime())["ui_render_view"](view_id="nonexistent")
    assert result.ok is False and result.data is None


def test_invalid_component_is_a_normal_ingestion_outcome():
    result = _data(_tools(_make_runtime())["ui_register_brick_views"](views=[{
        "id": "bad", "components": [{"id": "c1", "type": "nonexistent_type"}],
    }]))
    assert result.count == 0 and result.errors[0].id == "bad"


def test_typed_metadata_declares_strict_dtos():
    tools = _tools(_make_runtime())
    for tool in tools.values():
        assert tool._mcp_input_model.model_config["extra"] == "forbid"
        assert tool._mcp_output_model.model_config["extra"] == "forbid"
