"""Tests for the side-chat read-only tool policy (feature-map row 19)."""

from __future__ import annotations

from factory.mcp_utils.runtime.side_tool_policy import (
    classify_side_tool,
    is_side_read_only,
    partition_side_tools,
)


def test_deterministic_is_allowed():
    decision = classify_side_tool("deterministic")
    assert decision.allowed is True
    assert "read-only" in decision.reason


def test_operational_and_authoring_are_refused():
    for category in ("operational", "authoring"):
        decision = classify_side_tool(category)
        assert decision.allowed is False
        assert category in decision.reason
        assert "changes" in decision.reason


def test_uncategorised_is_refused_conservatively():
    decision = classify_side_tool(None)
    assert decision.allowed is False
    assert "read-only" in decision.reason  # "cannot be proven read-only"


def test_is_side_read_only_boolean():
    assert is_side_read_only("deterministic") is True
    assert is_side_read_only("operational") is False
    assert is_side_read_only(None) is False


def test_partition_splits_and_sorts():
    lookup = {
        "memory_stats": "deterministic",
        "session_archive": "operational",
        "agent_add_skill": "authoring",
        "graph_export": "deterministic",
    }
    allowed, refused = partition_side_tools(lookup)
    assert allowed == ["graph_export", "memory_stats"]
    assert refused == ["agent_add_skill", "session_archive"]
