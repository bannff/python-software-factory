"""Tests for the side-chat tool-dispatch gate (feature-map row 19)."""

from __future__ import annotations

from factory.mcp_utils.runtime.side_tool_gate import run_side_tool

LOOKUP = {
    "memory_stats": "deterministic",
    "graph.export": "deterministic",
    "graph_export": "deterministic",
    "session_archive": "operational",
}


def test_read_only_tool_is_dispatched():
    calls: list[tuple[str, dict]] = []

    def dispatch(name, args):
        calls.append((name, args))
        return {"rows": 3}

    outcome = run_side_tool(
        "memory_stats", {"scope": "all"}, category_lookup=LOOKUP, dispatch=dispatch,
    )
    assert outcome.ok is True
    assert outcome.result == {"rows": 3}
    assert calls == [("memory_stats", {"scope": "all"})]


def test_mutating_tool_is_refused_without_dispatch():
    calls: list = []
    outcome = run_side_tool(
        "session_archive", {"id": "x"}, category_lookup=LOOKUP,
        dispatch=lambda n, a: calls.append((n, a)),
    )
    assert outcome.ok is False
    assert "changes" in (outcome.refusal or "")
    assert calls == []  # dispatch never touched — the guarantee is structural


def test_unknown_tool_is_refused_conservatively():
    calls: list = []
    outcome = run_side_tool(
        "mystery_tool", {}, category_lookup=LOOKUP,
        dispatch=lambda n, a: calls.append(1),
    )
    assert outcome.ok is False
    assert calls == []


def test_dotted_name_resolves_via_normalised_key():
    outcome = run_side_tool(
        "graph.export", {}, category_lookup={"graph_export": "deterministic"},
        dispatch=lambda n, a: "ok",
    )
    assert outcome.ok is True
    assert outcome.result == "ok"
