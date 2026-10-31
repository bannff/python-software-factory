"""Tests for the LLM-backed side-turn planner (feature-map row 19)."""

from __future__ import annotations

from factory.mcp_utils.runtime.side_planner import build_llm_side_planner

LOOKUP = {"memory_stats": "deterministic", "graph_export": "deterministic", "session_archive": "operational"}


def test_parses_a_well_formed_plan_and_filters_to_allowed_tools():
    plan = build_llm_side_planner(
        complete=lambda prompt: '[{"tool": "memory_stats", "args": {"scope": "all"}}]',
        category_lookup=lambda: LOOKUP,
    )
    assert plan("how many memories?") == [("memory_stats", {"scope": "all"})]


def test_strips_markdown_fences():
    plan = build_llm_side_planner(
        complete=lambda prompt: '```json\n[{"tool": "graph_export", "args": {}}]\n```',
        category_lookup=lambda: LOOKUP,
    )
    assert plan("export the graph?") == [("graph_export", {})]


def test_drops_a_tool_not_in_the_allowed_read_only_set():
    plan = build_llm_side_planner(
        complete=lambda prompt: '[{"tool": "session_archive", "args": {}}]',
        category_lookup=lambda: LOOKUP,
    )
    assert plan("archive it") == []


def test_empty_plan_on_non_json_reply():
    plan = build_llm_side_planner(complete=lambda prompt: "I don't know", category_lookup=lambda: LOOKUP)
    assert plan("anything") == []


def test_empty_plan_on_empty_json_array():
    plan = build_llm_side_planner(complete=lambda prompt: "[]", category_lookup=lambda: LOOKUP)
    assert plan("hello") == []


def test_empty_plan_when_completion_raises():
    def boom(prompt: str) -> str:
        raise RuntimeError("no api key")
    plan = build_llm_side_planner(complete=boom, category_lookup=lambda: LOOKUP)
    assert plan("anything") == []


def test_empty_plan_when_no_read_only_tools_available():
    plan = build_llm_side_planner(
        complete=lambda prompt: '[{"tool": "x", "args": {}}]',
        category_lookup=lambda: {"session_archive": "operational"},
    )
    assert plan("anything") == []


def test_caps_plan_length_at_three():
    tools = '[{"tool":"memory_stats","args":{}},{"tool":"graph_export","args":{}},' \
        '{"tool":"memory_stats","args":{"a":1}},{"tool":"graph_export","args":{"b":2}}]'
    plan = build_llm_side_planner(complete=lambda prompt: tools, category_lookup=lambda: LOOKUP)
    assert len(plan("x")) == 3
