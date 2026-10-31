"""Shared constant: tool names that dashboard polling and refreshes produce.

Filtering these out at any read site (SSE stream, typed graph reads,
Timeline tab) prevents a self-amplifying feedback loop where dashboard
queries show up as new rows.

Tracked under bd python-factory-c39g (graph_list_recent_tool_invocations)
and bd python-factory-ff88 (eventual: filter at OTel write time so
noise tools never become ToolInvocation entities at all).
"""
from __future__ import annotations


POLL_NOISE: frozenset[str] = frozenset({
    "evals_get_run_result",
    "find_entities", "graph_find_entities", "graph_get_stats",
    "graph_get_capabilities", "graph_list_recent_tool_invocations",
    "graph_add_entity", "graph_add_relationship",
})

__all__ = ["POLL_NOISE"]
