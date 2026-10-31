"""Property tests for ``list_recent_tool_invocations`` (bd python-factory-c39g).

Sibling of ``test_typed_runs_properties.py`` — kept separate to stay
under the 200-LOC cap. Verifies the global recent-invocations reader
that drives the Companion-X Timeline tab.
"""

from __future__ import annotations

from hypothesis import given, strategies as st

from factory.graph.runtime.adapters.networkx_adapter import NetworkXGraph
from factory.graph.runtime.ports import Entity, Relationship

from ._typed_runs_fixtures import SETTINGS, created_at


def _add_invocation(
    graph: NetworkXGraph, inv_id: str, tool_name: str,
    created: str = "2026-01-01T00:00:00Z",
    session_id: str | None = None, workflow_run_id: str = "",
) -> None:
    """Test helper: add a ToolInvocation with optional Session join."""
    graph.add_entity(Entity(
        id=inv_id, type="ToolInvocation",
        properties={
            "tool_name": tool_name, "created_at": created,
            "workflow_run_id": workflow_run_id,
            "success": True, "latency_ms": 1,
            "brick_name": tool_name.split("_", 1)[0],
            "session_id": session_id,
        },
    ))
    if session_id:
        sid = f"session-{session_id}"
        graph.add_entity(Entity(
            id=sid, type="Session",
            properties={
                "id": sid, "agent_id": f"agent-{session_id}",
                "principal_id": f"principal-{session_id}",
            },
        ))
        graph.add_relationship(Relationship(
            id=f"contains-{sid}-{inv_id}",
            type="CONTAINS_INVOCATION",
            source_id=sid, target_id=inv_id,
        ))


class TestListRecentToolInvocations:
    """bd python-factory-c39g — global recent-invocations reader."""

    def test_empty_graph_returns_empty(self) -> None:
        graph = NetworkXGraph()
        result = graph.list_recent_tool_invocations(limit=100)
        assert list(result.raw or []) == []

    def test_round_trip_single_row(self) -> None:
        graph = NetworkXGraph()
        _add_invocation(
            graph, "inv-1", "agent_reason",
            created="2026-05-12T12:00:00Z", workflow_run_id="run-99",
        )
        rows = list(graph.list_recent_tool_invocations(limit=10).raw or [])
        assert len(rows) == 1
        assert rows[0]["tool_name"] == "agent_reason"
        assert rows[0]["workflow_run_id"] == "run-99"
        assert rows[0]["created_at"] == "2026-05-12T12:00:00Z"
        assert rows[0]["success"] is True

    def test_poll_noise_filtered(self) -> None:
        """find_entities et al. must not surface in result rows."""
        graph = NetworkXGraph()
        _add_invocation(graph, "inv-noise", "find_entities")
        _add_invocation(graph, "inv-noise2", "graph_get_stats")
        _add_invocation(graph, "inv-keep", "agent_reason")
        rows = list(graph.list_recent_tool_invocations(limit=100).raw or [])
        names = {r["tool_name"] for r in rows}
        assert "agent_reason" in names
        assert "find_entities" not in names
        assert "graph_get_stats" not in names

    def test_session_join(self) -> None:
        """Session.agent_id/principal_id come through one-hop traversal."""
        graph = NetworkXGraph()
        _add_invocation(graph, "inv-1", "agent_reason", session_id="s42")
        rows = list(graph.list_recent_tool_invocations(limit=10).raw or [])
        assert rows[0]["session_id"] == "session-s42"
        assert rows[0]["session_agent_id"] == "agent-s42"
        assert rows[0]["session_principal_id"] == "principal-s42"

    @given(seqs=st.lists(created_at, min_size=2, max_size=10, unique=True))
    @SETTINGS
    def test_sorted_desc_property(self, seqs: list[str]) -> None:
        """Rows always appear in created_at DESC order under arbitrary inserts."""
        graph = NetworkXGraph()
        for idx, ts in enumerate(seqs):
            _add_invocation(graph, f"inv-{idx}", f"tool_{idx}", created=ts)
        rows = list(
            graph.list_recent_tool_invocations(limit=len(seqs)).raw or [],
        )
        timestamps = [str(r.get("created_at", "")) for r in rows]
        assert timestamps == sorted(timestamps, reverse=True)

    @given(
        limit=st.integers(min_value=0, max_value=5),
        extras=st.integers(min_value=0, max_value=8),
    )
    @SETTINGS
    def test_limit_invariant(self, limit: int, extras: int) -> None:
        graph = NetworkXGraph()
        for idx in range(extras):
            _add_invocation(graph, f"inv-{idx}", f"tool_{idx}")
        rows = list(graph.list_recent_tool_invocations(limit=limit).raw or [])
        assert len(rows) <= limit

    def test_cross_adapter_parity_row_schema(self) -> None:
        """Pin the row keys the UI's mapTimelineHistoryRows consumes.

        Meta-architect Q8 / strands-expert findings: networkx and Neo4j
        adapters return semantically equivalent rows. Neo4j shape is
        verified in ``test_neo4j_typed_runs.py``; this test pins the
        networkx contract.
        """
        graph = NetworkXGraph()
        _add_invocation(
            graph, "inv-a", "agent_reason",
            created="2026-05-12T12:00:00Z", session_id="s1",
            workflow_run_id="r1",
        )
        rows = list(graph.list_recent_tool_invocations(limit=10).raw or [])
        for key in (
            "tool_name", "brick", "success", "latency_ms", "created_at",
            "error", "workflow_run_id", "args_summary", "caller",
            "result_summary", "session_id", "session_agent_id",
            "session_principal_id",
        ):
            assert key in rows[0], f"missing key {key} in row schema"
