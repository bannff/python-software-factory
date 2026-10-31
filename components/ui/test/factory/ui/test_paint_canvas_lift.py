"""Tests for ``lift_props_children`` (bd:python-factory-3hkqx round 3).

The producer-side lift normalizes agent's ``props.children`` shape into
canonical A2UI flat siblings with ``parent:`` refs before wire emit.
Pure helper — easy to unit + property test in isolation.
"""

from __future__ import annotations

from typing import Any

from hypothesis import given, settings, strategies as st

from factory.ui.mcp.paint_canvas_lift import lift_props_children


# --- Edge cases -----------------------------------------------------------


def test_empty_list_returns_empty():
    assert lift_props_children([]) == []


def test_non_dict_items_skipped():
    assert lift_props_children(["x", 42, None]) == []


def test_no_props_passthrough():
    comp = {"id": "a", "type": "Card"}
    assert lift_props_children([comp]) == [comp]


def test_props_without_children_passthrough():
    comp = {"id": "a", "type": "Card", "props": {"title": "Hello"}}
    assert lift_props_children([comp]) == [comp]


def test_empty_children_list_passthrough():
    """Empty list — no-op; existing props.children key stays unchanged."""
    comp = {"id": "a", "type": "Card", "props": {"title": "Hi", "children": []}}
    out = lift_props_children([comp])
    # Empty list isn't lifted (kids is empty), so original survives.
    assert len(out) == 1
    assert out[0]["id"] == "a"


# --- Core lifts -----------------------------------------------------------


def test_single_level_lift():
    """Card with one Text child → Card + Text(parent=Card)."""
    out = lift_props_children([{
        "id": "card-1", "type": "Card",
        "props": {"title": "Hello", "children": [
            {"id": "text-1", "type": "Text", "props": {"value": "world"}},
        ]},
    }])
    assert len(out) == 2
    assert out[0]["id"] == "card-1"
    assert out[0]["props"] == {"title": "Hello"}
    assert "children" not in out[0].get("props", {})
    assert "parent" not in out[0]
    assert out[1] == {
        "id": "text-1", "type": "Text",
        "props": {"value": "world"}, "parent": "card-1",
    }


def test_multi_level_lift():
    """Card → Card → Text becomes 3 flat siblings with chained parent."""
    out = lift_props_children([{
        "id": "outer", "type": "Card",
        "props": {"children": [{
            "id": "inner", "type": "Card",
            "props": {"children": [
                {"id": "leaf", "type": "Text", "props": {"value": "x"}},
            ]},
        }]},
    }])
    assert [c["id"] for c in out] == ["outer", "inner", "leaf"]
    assert "parent" not in out[0]
    assert out[1]["parent"] == "outer"
    assert out[2]["parent"] == "inner"


def test_mixed_nested_and_standalone():
    """Top-level [Card[Text], Standalone] → 3 entries."""
    out = lift_props_children([
        {"id": "card", "type": "Card",
         "props": {"children": [
             {"id": "txt", "type": "Text", "props": {"value": "x"}},
         ]}},
        {"id": "alone", "type": "Alert", "props": {"message": "hey"}},
    ])
    ids = [c["id"] for c in out]
    assert ids == ["card", "txt", "alone"]
    assert out[1]["parent"] == "card"
    assert "parent" not in out[2]


def test_existing_parent_preserved():
    """If host already has ``parent:`` set, lifted children get THIS host's id
    as parent (not the host's parent). bd-3hkqx Q4 last-write-wins is fine."""
    out = lift_props_children([{
        "id": "card", "type": "Card", "parent": "page",
        "props": {"children": [
            {"id": "txt", "type": "Text", "props": {"value": "x"}},
        ]},
    }])
    assert len(out) == 2
    assert out[0]["parent"] == "page"  # host preserved
    assert out[1]["parent"] == "card"  # child points at host


def test_child_without_id_dropped_at_validation():
    """Child without an ``id`` walks but produces no entry — the recursion
    only descends when the host has an id, so a missing-id child gets
    appended but its sub-tree is orphaned. validate_a2ui catches the
    missing id and the producer returns a structured error."""
    out = lift_props_children([{
        "id": "card", "type": "Card",
        "props": {"children": [{"type": "Text"}]},  # no id on child
    }])
    # Child appears in output (the lift doesn't validate ids — that's
    # validate_a2ui's job) but with parent=card and no id of its own.
    assert len(out) == 2
    assert "id" not in out[1]
    assert out[1]["parent"] == "card"


# --- Hypothesis properties ------------------------------------------------


_simple_text = st.fixed_dictionaries({
    "id": st.text(min_size=1, max_size=6),
    "type": st.just("Text"),
    "props": st.dictionaries(
        keys=st.sampled_from(["value", "variant"]),
        values=st.text(max_size=8), max_size=2),
})

_simple_card = st.fixed_dictionaries({
    "id": st.text(min_size=1, max_size=6),
    "type": st.just("Card"),
    "props": st.fixed_dictionaries(
        {"title": st.text(max_size=10),
         "children": st.lists(_simple_text, max_size=3)},
    ),
})


def _all_ids(comps: list[dict[str, Any]]) -> set[str]:
    return {c["id"] for c in comps if isinstance(c.get("id"), str)}


@given(comps=st.lists(_simple_card, max_size=4))
@settings(max_examples=50, deadline=None)
def test_idempotent_under_double_lift(comps):
    """``lift(lift(x)) == lift(x)`` — once flat, applying the lift again
    is a no-op (no ``props.children`` left to lift)."""
    once = lift_props_children(comps)
    twice = lift_props_children(once)
    assert once == twice


@given(comps=st.lists(_simple_card, max_size=4))
@settings(max_examples=50, deadline=None)
def test_every_parent_ref_resolves(comps):
    """Every output entry's ``parent`` ref (if present) is the id of some
    other entry in the output."""
    out = lift_props_children(comps)
    ids = _all_ids(out)
    for entry in out:
        parent = entry.get("parent")
        if parent is not None:
            assert parent in ids, f"orphan parent ref: {parent}"
