"""Tests for ``ui_paint_chat`` (bd:python-factory-zg93f).

Carrier #1 of the four-carrier model — sibling of ``ui_paint_canvas``
without the ``_a2ui_canvas`` sentinel. Returns ``{components, name}``
directly so the wildcard ``useDefaultRenderTool`` predicate at
``frontends/next-dashboard/lib/copilotkit/tool-renderers.tsx:54-86``
(``Array.isArray(parsed.components)``) paints it via ``<InlineView>``.

Verdicts:
- meta-architect ``d0cdb475-f014-41d6-8288-1e0e8641bff0``
- strands-expert ``293c185e-4d29-4728-b6e7-eee04d633ff3``
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from hypothesis import given, settings, strategies as st

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


_VALID_PAYLOAD = {
    "components": [
        {"id": "c1", "type": "card", "props": {"title": "Hello"}},
        {"id": "t1", "type": "text", "props": {"content": "world"}},
    ],
    "name": "Demo",
}


# --- Happy path -----------------------------------------------------------


def test_valid_payload_returns_components_and_name():
    """Returns ``{components, name}`` directly — no ``_a2ui_canvas`` sentinel."""
    result = _make_tool()(payload=_VALID_PAYLOAD)
    assert "error" not in result
    assert result["components"] == _VALID_PAYLOAD["components"]
    # Payload-supplied name wins over the default header.
    assert result["name"] == "Demo"
    # Carrier #1 contract: no sentinel, no canvas-specific keys.
    assert "_a2ui_canvas" not in result
    assert "target" not in result


def test_default_name_is_inline_view():
    """When neither arg ``name`` nor ``payload.name`` set, default to header text."""
    result = _make_tool()(payload={"components": []})
    assert result["name"] == "Inline View"


def test_arg_name_overrides_payload_name():
    """The arg ``name`` is the inline-card header override."""
    result = _make_tool()(payload=_VALID_PAYLOAD, name="Custom Header")
    assert result["name"] == "Custom Header"


def test_arg_name_overrides_when_payload_has_no_name():
    result = _make_tool()(
        payload={"components": []}, name="My Block")
    assert result["name"] == "My Block"


def test_payload_name_used_when_no_arg_name():
    """Payload-supplied ``name`` falls through when arg is not given."""
    result = _make_tool()(payload=_VALID_PAYLOAD)
    assert result["name"] == "Demo"


def test_empty_components_is_valid():
    """Empty paint produces an empty inline card — emit through same path."""
    result = _make_tool()(payload={"components": []})
    assert "error" not in result
    assert result["components"] == []
    assert isinstance(result["name"], str)


# --- Catalog allowlist (mirrors paint_canvas behaviour) -------------------


def test_unknown_component_type_rejected():
    """Catalog allowlist — unknown types are rejected with a structured error."""
    result = _make_tool()(
        payload={"components": [{"id": "x", "type": "heading"}]})
    assert "Unknown component type" in result.get("error", "")
    # Error lists valid catalog entries so the agent self-corrects.
    assert "Card" in result["error"]


def test_known_component_types_accepted_case_insensitive():
    """PascalCase, lowercase, and underscore aliases all accepted."""
    tool = _make_tool()
    for tn in ("Card", "card", "Text", "Sparkline", "item_list"):
        result = tool(payload={"components": [{"id": "x", "type": tn}]})
        assert "error" not in result, f"{tn} should be accepted"


# --- props.children lift (sibling behaviour to paint_canvas) --------------
# Lift integration tests live in ``test_paint_chat_nesting.py`` to keep
# this file under the 200 LOC tenet (mirrors the canvas split).


# --- Validation envelope (never raise) ------------------------------------


def test_invalid_payload_type_fails_at_ingress():
    """Non-dict, non-JSON-string payloads raise at the typed ingress,
    never a silent default."""
    with pytest.raises(Exception):
        _make_tool()(payload=42)  # type: ignore[arg-type]


def test_stringified_json_payload_matches_dict_path():
    """LLMs serialize nested object args as JSON strings — coerce, don't reject.

    Regression: ``payload`` sent as ``"{\"components\": [...]}"`` used to
    bounce off ``_error_for_payload`` with ``payload must be an object…``.
    """
    as_dict = _make_tool()(payload=_VALID_PAYLOAD)
    as_str = _make_tool()(payload=json.dumps(_VALID_PAYLOAD))
    assert as_str == as_dict
    assert as_str["components"] == _VALID_PAYLOAD["components"]
    assert as_str["name"] == "Demo"


def test_malformed_json_string_payload_fails_loudly():
    """A string that is not valid JSON raises at the ingress boundary —
    mirrors the evals_record_run coercion posture (bd python-factory-38veu)."""
    with pytest.raises(Exception):
        _make_tool()(payload="{not valid json")  # type: ignore[arg-type]


def test_invalid_a2ui_payload_returns_error_envelope():
    """Malformed component entries surface validate_a2ui's error path."""
    result = _make_tool()(payload={"components": "not-a-list"})
    assert "error" in result
    assert "Invalid A2UI payload" in result["error"]


# --- Hypothesis property test ---------------------------------------------


_simple_component = st.fixed_dictionaries({
    "id": st.text(min_size=1, max_size=8),
    "type": st.sampled_from(["card", "text", "list", "form", "item_list"]),
    "props": st.dictionaries(
        keys=st.text(min_size=1, max_size=6),
        values=st.one_of(st.text(max_size=8), st.integers(), st.booleans()),
        max_size=2),
})

_payload_strat = st.fixed_dictionaries(
    {"components": st.lists(_simple_component, max_size=4)},
    optional={"name": st.text(min_size=1, max_size=12)},
)


@given(payload=_payload_strat, override=st.one_of(st.none(), st.text(min_size=1, max_size=10)))
@settings(max_examples=30, deadline=None)
def test_property_tool_always_returns_dict_with_invariants(payload, override):
    """Tool always returns dict; success → carrier #1 wire shape holds."""
    seen: set[str] = set()
    components = [c for c in payload["components"]
                  if not (c["id"] in seen or seen.add(c["id"]))]
    payload = {**payload, "components": components}
    result = _make_tool()(payload=payload, name=override)
    assert isinstance(result, dict)
    if "error" in result:
        assert isinstance(result["error"], str)
        return
    # Wire-shape invariants — what the wildcard predicate sees.
    assert isinstance(result["components"], list)
    assert isinstance(result["name"], str)
    # No canvas sentinel, no STATE_DELTA leakage.
    assert "_a2ui_canvas" not in result
