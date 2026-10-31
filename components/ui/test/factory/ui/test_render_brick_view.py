"""Typed MCP tests for the inline ``ui_render_brick_view`` A2UI carrier."""
from __future__ import annotations

from typing import Any

import pytest
from hypothesis import given, settings, strategies as st

from factory.mcp_utils.interface import ToolResult, get_service, set_service
from factory.ui.mcp.render_brick_view import register


class _Harness:
    def __init__(self) -> None:
        self.tools: dict[str, Any] = {}

    def tool(self):
        def decorate(fn):
            self.tools[fn.__name__] = fn
            return fn
        return decorate


def _make_tool() -> Any:
    mcp = _Harness()
    register(mcp, get_runtime=lambda: None)
    return mcp.tools["ui_render_brick_view"]


@pytest.fixture
def restore_invoker():
    previous = get_service("tool_invoker")
    yield
    set_service("tool_invoker", previous)


def _set_invoker(views: Any) -> None:
    set_service("tool_invoker", lambda _tool_name, **_kwargs: views)


_KB_VIEW = {
    "id": "kb-search", "name": "Knowledge Base",
    "components": [{"id": "form", "type": "form", "props": {"action": "kb_search"},
                    "children": [{"id": "q", "type": "text", "props": {"content": "Q"}}]}],
}


def _data(result: ToolResult):
    assert result.ok is True, result
    return result.data


def test_round_trip_preserves_flat_a2ui_carrier(restore_invoker):
    _set_invoker([_KB_VIEW])
    result = _data(_make_tool()(brick_name="kb"))
    assert result.name == "Knowledge Base"
    assert all("children" not in component for component in result.components)
    assert next(c for c in result.components if c["id"] == "q")["parent"] == "form"


def test_view_id_selection(restore_invoker):
    _set_invoker([_KB_VIEW, {"id": "evals", "name": "Evals", "components": []}])
    assert _data(_make_tool()(brick_name="any", view_id="evals")).name == "Evals"


@pytest.mark.parametrize("views,view_id", [([], None), ([_KB_VIEW], "missing")])
def test_domain_absence_is_failed_outer_envelope(restore_invoker, views, view_id):
    _set_invoker(views)
    result = _make_tool()(brick_name="kb", view_id=view_id)
    assert result.ok is False and result.data is None


def test_missing_invoker_is_failed_outer_envelope(restore_invoker):
    set_service("tool_invoker", None)
    result = _make_tool()(brick_name="kb")
    assert result.ok is False and "tool_invoker" in result.error


def test_invoker_exception_is_failed_outer_envelope(restore_invoker):
    def boom(*_args, **_kwargs):
        raise RuntimeError("boom")
    set_service("tool_invoker", boom)
    result = _make_tool()(brick_name="kb")
    assert result.ok is False and "boom" in result.error


def test_metadata_declares_strict_dtos():
    tool = _make_tool()
    assert tool._mcp_input_model.model_config["extra"] == "forbid"
    assert tool._mcp_output_model.model_config["extra"] == "forbid"


@given(name=st.text(min_size=1, max_size=20))
@settings(max_examples=20, deadline=None)
def test_property_success_always_has_a2ui_carrier(name):
    previous = get_service("tool_invoker")
    set_service("tool_invoker", lambda *_args, **_kwargs: [{
        "id": "view", "name": name,
        "components": [{"id": "component", "type": "text", "props": {}}],
    }])
    try:
        result = _data(_make_tool()(brick_name="any"))
    finally:
        set_service("tool_invoker", previous)
    assert result.name == name
    assert isinstance(result.components, list)
