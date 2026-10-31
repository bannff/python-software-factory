"""Tests for the side-turn executor (feature-map row 19)."""

from __future__ import annotations

from factory.mcp_utils.runtime.side_conversation import SideConversationStore
from factory.mcp_utils.runtime.side_turn import run_side_turn

LOOKUP = {"memory_stats": "deterministic", "session_archive": "operational"}


def test_read_only_tool_runs_and_is_recorded():
    store = SideConversationStore()
    dispatched: list = []

    def dispatch(name, args):
        dispatched.append(name)
        return {"total": 7}

    result = run_side_turn(
        store, "slot-1", "how many memories?",
        plan=lambda q: [("memory_stats", {})],
        category_lookup=LOOKUP, dispatch=dispatch,
    )
    assert result.refused == []
    assert dispatched == ["memory_stats"]
    convo = store.get("slot-1")
    assert convo.turns[0].role == "user"
    assert "memory_stats" in convo.turns[1].text
    assert "total" in convo.turns[1].text


def test_mutating_tool_is_refused_and_never_dispatched():
    store = SideConversationStore()
    dispatched: list = []
    result = run_side_turn(
        store, "s", "archive it",
        plan=lambda q: [("session_archive", {"id": "x"})],
        category_lookup=LOOKUP, dispatch=lambda n, a: dispatched.append(n),
    )
    assert result.refused == ["session_archive"]
    assert dispatched == []  # structural no-change guarantee
    assert "refused" in store.get("s").turns[1].text


def test_empty_plan_records_only_the_user_turn():
    store = SideConversationStore()
    result = run_side_turn(
        store, "s", "hello", plan=lambda q: [],
        category_lookup=LOOKUP, dispatch=lambda n, a: None,
    )
    assert [t.role for t in result.turns] == ["user"]
    assert result.refused == []


def test_mixed_plan_partitions_correctly():
    store = SideConversationStore()
    result = run_side_turn(
        store, "s", "stats then archive",
        plan=lambda q: [("memory_stats", {}), ("session_archive", {})],
        category_lookup=LOOKUP, dispatch=lambda n, a: "ok",
    )
    assert result.refused == ["session_archive"]
    # user + 2 tool turns
    assert len(store.get("s").turns) == 3
