"""Integration tests for the ``props.children`` lift in ``ui_paint_chat``.

Carved out of ``test_paint_chat.py`` to keep that file under 200 LOC,
mirroring the ``test_paint_canvas_nesting.py`` split (bd:python-factory-3hkqx
round 3 / bd:python-factory-zg93f). These verify the producer-side lift
end-to-end: from agent-emitted nested ``props.children`` to canonical
flat siblings on the inline-chat wire.
"""

from __future__ import annotations

from typing import Any

from factory.ui.mcp.paint_chat import register


class _Harness:
    def __init__(self) -> None:
        self.tools: dict[str, Any] = {}

    def tool(self):
        def deco(fn):
            self.tools[fn.__name__] = fn
            return fn
        return deco


def _make_tool() -> Any:
    mcp = _Harness()
    register(mcp, get_runtime=lambda: None)
    tool = mcp.tools["ui_paint_chat"]

    def invoke(**kwargs: Any) -> dict[str, Any]:
        result = tool(**kwargs)
        return {"error": result.error} if not result.ok else result.data.model_dump(by_alias=True)

    return invoke


def test_props_children_lifted_to_parent_refs():
    """Card{props.children:[Text]} normalised to flat siblings with parent: refs."""
    result = _make_tool()(
        payload={"components": [{
            "id": "card1", "type": "Card",
            "props": {"title": "Hello", "children": [
                {"id": "txt1", "type": "Text", "props": {"value": "world"}},
            ]},
        }]})
    assert "error" not in result
    components = result["components"]
    assert len(components) == 2
    assert components[0]["id"] == "card1"
    assert "children" not in components[0].get("props", {})
    assert components[1] == {
        "id": "txt1", "type": "Text",
        "props": {"value": "world"}, "parent": "card1",
    }


def test_three_deep_nesting_chains_parents():
    """Card→Card→Text via props.children produces 3 flat siblings."""
    result = _make_tool()(
        payload={"components": [{
            "id": "outer", "type": "Card",
            "props": {"children": [{
                "id": "inner", "type": "Card",
                "props": {"children": [
                    {"id": "leaf", "type": "Text", "props": {"value": "x"}},
                ]},
            }]},
        }]})
    assert "error" not in result
    components = result["components"]
    assert [c["id"] for c in components] == ["outer", "inner", "leaf"]
    assert components[1]["parent"] == "outer"
    assert components[2]["parent"] == "inner"


def test_props_children_without_id_surfaces_validation_error():
    """Lift descends into props.children; validate_a2ui catches missing id
    so the agent self-corrects."""
    result = _make_tool()(
        payload={"components": [{
            "id": "card", "type": "Card",
            "props": {"children": [{"type": "Text"}]},
        }]})
    assert "error" in result
    assert "Missing required 'id'" in result["error"]
