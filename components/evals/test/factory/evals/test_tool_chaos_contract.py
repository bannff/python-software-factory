"""Contract tests for bounded declarative SDK-native tool chaos."""
from __future__ import annotations

import json

import pytest
from hypothesis import given, strategies as st

from factory.evals.runtime.tool_chaos_contract import (
    MAX_ITEMS,
    MAX_STRING,
    bounded_value,
    fault_conditions,
    selected_tools,
    validate_cases,
)


def test_allowlist_requires_nonempty_unique_static_subset():
    assert selected_tools(["knowledge_search"]) == ("knowledge_search",)
    with pytest.raises(ValueError, match="nonempty unique"):
        selected_tools(["knowledge_search", "knowledge_search"])
    with pytest.raises(ValueError, match="unknown tool"):
        selected_tools(["caller_callable"])


def test_native_effect_translation_rejects_unknown_tools_and_parameters():
    conditions = fault_conditions([{
        "condition": "search-timeout",
        "tool_effects": {"knowledge_search": [{"effect_type": "timeout", "error_message": "late"}]},
    }], ("knowledge_search",))
    from strands_evals.chaos import Timeout
    effect = conditions[0]["effects"]["tool_effects"]["knowledge_search"][0]
    assert isinstance(effect, Timeout)
    assert effect.effect_type == "timeout"
    with pytest.raises(ValueError, match="selected tool"):
        fault_conditions([{"condition": "bad", "tool_effects": {"unknown": [{"effect_type": "timeout"}]}}], ("knowledge_search",))
    with pytest.raises(ValueError, match="invalid remove_fields"):
        fault_conditions([{"condition": "ratio", "tool_effects": {"knowledge_search": [{"effect_type": "remove_fields", "remove_ratio": 1.1}]}}], ("knowledge_search",))
    with pytest.raises(ValueError, match="unsupported parameters"):
        fault_conditions([{"condition": "bad", "tool_effects": {"knowledge_search": [{"effect_type": "timeout", "code": 1}]}}], ("knowledge_search",))


def test_native_effect_limits_and_case_limits_are_enforced():
    with pytest.raises(ValueError, match="max_length"):
        fault_conditions([{"condition": "long", "tool_effects": {"knowledge_search": [{"effect_type": "truncate_fields", "max_length": MAX_STRING + 1}]}}], ("knowledge_search",))
    with pytest.raises(ValueError, match="4096"):
        validate_cases([{"input": "x" * 4097}])


@st.composite
def _json_values(draw, depth: int = 0):
    atoms = st.one_of(st.none(), st.booleans(), st.integers(), st.text(max_size=2000))
    if depth >= 3:
        return draw(atoms)
    return draw(st.recursive(
        atoms,
        lambda child: st.one_of(st.lists(child, max_size=24), st.dictionaries(st.text(max_size=80), child, max_size=24)),
        max_leaves=32,
    ))


@given(value=_json_values())
def test_bounded_evidence_is_json_safe_and_recursively_limited(value):
    bounded = bounded_value(value)
    assert json.loads(json.dumps(bounded, allow_nan=False)) == bounded

    def assert_bounds(item, depth=0):
        assert depth <= 4
        if isinstance(item, str):
            assert len(item) <= MAX_STRING
        if isinstance(item, dict):
            assert len(item) <= MAX_ITEMS
            for key, child in item.items():
                assert len(key) <= 64
                assert_bounds(child, depth + 1)
        if isinstance(item, list):
            assert len(item) <= MAX_ITEMS
            for child in item:
                assert_bounds(child, depth + 1)
    assert_bounds(bounded)
