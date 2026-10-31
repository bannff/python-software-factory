"""Snapshot test pinning the chat-tool-result shape for multi-agent runs.

bd-qev3 added ``run_id`` to ``SwarmResult`` and ``GraphResult`` so the
chat tool result body carries a join key for the FE
``<SubagentChildRows>`` filter. This file mirrors the
``EXPECTED_AGENT_EVENTS`` pattern from
``test_event_schema_snapshot.py`` — a frozenset per result type IS the
contract: any silent field drop has to update this dict and is visible
in PR review.

Downstream consumers of ``SwarmResult.to_dict()`` /
``GraphResult.to_dict()`` (mcp/tools.py invoke_swarm/invoke_graph,
mcp/launch_tools.py agent_launch_swarm, mcp/async_tools.py polled
state, executors/orchestrator.py spread) all forward the dict to the
chat-tool-result body verbatim — pinning the dict keys here pins the
downstream contract.
"""
from __future__ import annotations

from factory.agent.runtime.ports import GraphResult, SwarmResult


EXPECTED_SWARM_RESULT_KEYS: frozenset[str] = frozenset({
    "status",
    "output",
    "node_history",
    "execution_time",
    "accumulated_usage",
    "accumulated_metrics",
    "execution_count",
    "per_node_results",
    "run_id",
})


EXPECTED_GRAPH_RESULT_KEYS: frozenset[str] = frozenset({
    "status",
    "execution_order",
    "results",
    "execution_time",
    "node_errors",
    "node_statuses",
    "structured_outputs",
    "session_id",
    "cached",
    "run_id",
})


def test_swarm_result_to_dict_shape_unset_run_id() -> None:
    """Default-constructed SwarmResult.to_dict() carries every contract key."""
    keys = frozenset(SwarmResult(status="ok", output="hi").to_dict().keys())
    assert keys == EXPECTED_SWARM_RESULT_KEYS


def test_swarm_result_to_dict_shape_with_run_id() -> None:
    """Run-id-tagged SwarmResult.to_dict() preserves the join key."""
    payload = SwarmResult(status="ok", output="hi", run_id="r-abc").to_dict()
    assert frozenset(payload.keys()) == EXPECTED_SWARM_RESULT_KEYS
    assert payload["run_id"] == "r-abc"


def test_graph_result_to_dict_shape_unset_run_id() -> None:
    """Default-constructed GraphResult.to_dict() carries every contract key."""
    keys = frozenset(GraphResult(status="ok").to_dict().keys())
    assert keys == EXPECTED_GRAPH_RESULT_KEYS


def test_graph_result_to_dict_shape_with_run_id() -> None:
    """Run-id-tagged GraphResult.to_dict() preserves the join key."""
    payload = GraphResult(status="ok", run_id="r-xyz").to_dict()
    assert frozenset(payload.keys()) == EXPECTED_GRAPH_RESULT_KEYS
    assert payload["run_id"] == "r-xyz"
