"""Tests for the side-chat service facade (feature-map row 19)."""

from __future__ import annotations

from factory.mcp_utils.runtime.side_chat_service import SideChatService

LOOKUP = {"memory_stats": "deterministic", "session_archive": "operational"}


def make_service(plan):
    calls: list[str] = []
    svc = SideChatService(
        planner=plan,
        category_lookup=lambda: LOOKUP,
        dispatch=lambda name, args: calls.append(name) or {"ok": name},
    )
    return svc, calls


def test_open_is_idempotent_and_returns_turns():
    svc, _ = make_service(lambda q: [])
    first = svc.open("slot-1")
    assert first.slot == "slot-1"
    assert first.turns == []
    assert svc.is_open("slot-1") is True
    svc.turn("slot-1", "hello")
    # reopening surfaces the accumulated transcript, doesn't wipe it
    assert len(svc.open("slot-1").turns) >= 1


def test_turn_runs_read_only_tool_and_refuses_mutation():
    svc, calls = make_service(lambda q: [("memory_stats", {}), ("session_archive", {})])
    result = svc.turn("s", "stats then archive")
    assert result.refused == ["session_archive"]
    assert calls == ["memory_stats"]  # only the read-only tool was dispatched


def test_close_discards():
    svc, _ = make_service(lambda q: [])
    svc.open("s")
    assert svc.close("s") is True
    assert svc.is_open("s") is False
    assert svc.close("s") is False


def test_category_lookup_is_resolved_per_turn():
    resolved = {"n": 0}

    def lookup():
        resolved["n"] += 1
        return LOOKUP

    svc = SideChatService(planner=lambda q: [], category_lookup=lookup, dispatch=lambda n, a: None)
    svc.turn("s", "a")
    svc.turn("s", "b")
    assert resolved["n"] == 2  # fresh lookup each turn (bricks load lazily)
