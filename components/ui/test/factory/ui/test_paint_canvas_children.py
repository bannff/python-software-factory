"""Issue #224: ``ui_paint_canvas`` must refuse malformed ``children`` at the boundary.

Bare strings / typeless objects in ``children`` and non-object entries in
``props.children`` used to be accepted or silently dropped, which painted
the blank "Unknown component" card. They now return a typed refusal.
"""

from __future__ import annotations

from typing import Any

import pytest

from factory.ui.mcp.paint_canvas import register
from factory.ui.runtime.a2ui import validate_a2ui


class _Harness:
    def __init__(self) -> None:
        self.tools: dict[str, Any] = {}

    def tool(self):
        def deco(fn):
            self.tools[fn.__name__] = fn
            return fn
        return deco


def _paint(components: list[Any]):
    mcp = _Harness()
    register(mcp, get_runtime=lambda: None)
    return mcp.tools["ui_paint_canvas"](target="live", payload={"components": components})


@pytest.mark.parametrize("children", [
    ["hello bare"],
    [{"id": "n1", "props": {}}],
    [{"id": "n1", "type": "NopeWidget"}],
    "not-a-list",
    [42],
])
def test_malformed_top_level_children_refused(children):
    result = _paint([{"id": "c1", "type": "Card", "children": children}])
    assert not result.ok
    assert "children" in result.error


def test_list_children_strings_refused():
    result = _paint([{"id": "l1", "type": "List", "children": ["Item one", "Item two"]}])
    assert not result.ok
    assert "children" in result.error


@pytest.mark.parametrize("kids", [["hello bare"], [{"id": "t", "type": "Text"}, 7]])
def test_props_children_non_object_refused_not_dropped(kids):
    result = _paint([{"id": "c1", "type": "Card", "props": {"children": kids}}])
    assert not result.ok
    assert "props.children" in result.error


def test_children_referencing_existing_ids_accepted():
    result = _paint([
        {"id": "c1", "type": "Card", "children": ["t1"]},
        {"id": "t1", "type": "Text", "props": {"value": "hi"}},
    ])
    assert result.ok


def test_schema_reports_dangling_child_reference():
    errors = validate_a2ui({"components": [
        {"id": "c1", "type": "Card", "children": ["ghost"]},
    ]})
    assert errors and "ghost" in errors[0].message
