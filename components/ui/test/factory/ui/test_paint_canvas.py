"""Tests for ``ui_paint_canvas`` (bd-D, EPIC python-factory-iet5).

Carrier #2 of the four-carrier model. The tool emits a tagged result
``{_a2ui_canvas: {target, mode, payload}, ...}`` that
``factory.agent.plugins.state_delta_plugin`` (separate Python brick)
detects and converts to a ``StateDeltaEvent`` for the AG-UI mapper.

These tests verify the **producer side** in isolation — the sentinel
shape, validation envelope, and property-based invariants. The
plugin-side detection is tested in
``components/agent/test/factory/agent/test_state_delta_plugin.py``.
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from hypothesis import given, settings, strategies as st

from factory.ui.mcp.paint_canvas import register


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
    tool = mcp.tools["ui_paint_canvas"]

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


def test_valid_target_returns_a2ui_canvas_sentinel():
    """Default mode='snapshot' produces sentinel with full normalized payload."""
    result = _make_tool()(target="graph", payload=_VALID_PAYLOAD)
    assert "error" not in result
    assert result["_a2ui_canvas"] == {
        "target": "graph",
        "mode": "snapshot",
        "payload": {"components": _VALID_PAYLOAD["components"], "name": "Demo"},
    }
    assert result["rendered"] is True
    assert result["target"] == "graph"
    assert result["mode"] == "snapshot"
    assert result["component_count"] == 2


def test_default_mode_is_snapshot():
    result = _make_tool()(target="findings", payload={"components": []})
    assert result["_a2ui_canvas"]["mode"] == "snapshot"


def test_delta_mode_round_trips_through_sentinel():
    result = _make_tool()(
        target="timeline", payload=_VALID_PAYLOAD, mode="delta")
    assert result["_a2ui_canvas"]["mode"] == "delta"
    assert result["_a2ui_canvas"]["target"] == "timeline"


def test_name_defaults_to_target_when_missing():
    """Spec: ``payload.name`` defaults to ``target`` if not provided."""
    result = _make_tool()(target="live", payload={"components": []})
    assert result["_a2ui_canvas"]["payload"]["name"] == "live"


def test_empty_components_is_valid():
    """Empty paint clears the slot — emit it through the same path."""
    result = _make_tool()(target="graph", payload={"components": []})
    assert "error" not in result
    assert result["component_count"] == 0
    assert result["_a2ui_canvas"]["payload"]["components"] == []


def test_each_valid_target_accepted():
    tool = _make_tool()
    for target in ("graph", "timeline", "findings", "live"):
        result = tool(target=target, payload={"components": []})
        assert "error" not in result
        assert result["_a2ui_canvas"]["target"] == target


def test_legacy_canvas_target_rejected():
    """bd-3hkqx — slot renamed canvas → live."""
    result = _make_tool()(target="canvas", payload={"components": []})  # type: ignore[arg-type]
    assert "error" in result and "live" in result["error"]


def test_unknown_component_type_rejected():
    """bd-3hkqx — agent must use catalog types."""
    result = _make_tool()(
        target="live",
        payload={"components": [{"id": "x", "type": "heading"}]})
    assert "Unknown component type" in result.get("error", "")
    assert "Card" in result["error"]


def test_known_component_types_accepted_case_insensitive():
    """PascalCase, lowercase, and underscore aliases all accepted."""
    tool = _make_tool()
    for tn in ("Card", "card", "Text", "Sparkline", "item_list"):
        result = tool(target="live", payload={"components": [{"id": "x", "type": tn}]})
        assert "error" not in result, f"{tn} should be accepted"


# bd-3hkqx: nesting tests in ``test_paint_canvas_nesting.py``;
# lift unit + property tests in ``test_paint_canvas_lift.py``.


# --- Validation envelope (never raise) -------------------------------------


def test_invalid_target_returns_error_envelope():
    """Bad target → error envelope, NOT raise — tool result must not stall the run."""
    result = _make_tool()(target="bogus", payload={"components": []})  # type: ignore[arg-type]
    assert "error" in result
    assert "Invalid target" in result["error"]
    assert "_a2ui_canvas" not in result


def test_invalid_mode_returns_error_envelope():
    result = _make_tool()(
        target="graph", payload={"components": []}, mode="weird")  # type: ignore[arg-type]
    assert "error" in result
    assert "Invalid mode" in result["error"]


def test_invalid_payload_type_fails_at_ingress():
    """Non-dict, non-JSON-string payloads raise at the typed ingress
    (SchemaMigrationError from migrate_to), never a silent default."""
    with pytest.raises(Exception):
        _make_tool()(target="graph", payload=42)  # type: ignore[arg-type]


def test_stringified_json_payload_matches_dict_path():
    """LLMs serialize nested object args as JSON strings — coerce, don't reject.

    Regression: ``payload`` sent as ``"{\"components\": [...]}"`` used to
    bounce off ``_error_for_payload`` with ``payload must be an object…``,
    leaving the canvas stuck at 'Awaiting agent paint…'.
    """
    as_dict = _make_tool()(target="live", payload=_VALID_PAYLOAD)
    as_str = _make_tool()(target="live", payload=json.dumps(_VALID_PAYLOAD))
    assert as_str == as_dict
    assert "_a2ui_canvas" in as_str
    assert as_str["_a2ui_canvas"]["payload"]["components"] == (
        _VALID_PAYLOAD["components"]
    )


def test_malformed_json_string_payload_fails_loudly():
    """A string that is not valid JSON raises at the ingress boundary —
    mirrors the evals_record_run coercion posture (bd python-factory-38veu)."""
    with pytest.raises(Exception):
        _make_tool()(target="live", payload="{not valid json")  # type: ignore[arg-type]


def test_invalid_a2ui_payload_returns_error_envelope():
    """Malformed component entries surface validate_a2ui's error path."""
    result = _make_tool()(target="graph", payload={"components": "not-a-list"})
    assert "error" in result
    assert "Invalid A2UI payload" in result["error"]


# --- Hypothesis property test ----------------------------------------------


_TARGETS = st.sampled_from(["graph", "timeline", "findings", "live"])
_MODES = st.sampled_from(["snapshot", "delta"])

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


@given(target=_TARGETS, payload=_payload_strat, mode=_MODES)
@settings(max_examples=30, deadline=None)
def test_property_tool_always_returns_dict_with_invariants(target, payload, mode):
    """Tool always returns dict; success → ``_a2ui_canvas.target`` matches."""
    seen: set[str] = set()
    components = [c for c in payload["components"]
                  if not (c["id"] in seen or seen.add(c["id"]))]
    payload = {**payload, "components": components}
    result = _make_tool()(target=target, payload=payload, mode=mode)
    assert isinstance(result, dict)
    if "error" in result:
        assert isinstance(result["error"], str)
        return
    sentinel = result["_a2ui_canvas"]
    assert sentinel["target"] == target and sentinel["mode"] == mode
    assert isinstance(sentinel["payload"]["components"], list)
    assert isinstance(sentinel["payload"]["name"], str)
