"""Tests for Neo4j ``list_recent_tool_invocations`` (bd python-factory-c39g).

Sibling of ``test_neo4j_typed_runs.py`` — kept separate to stay under
the 200-LOC cap. Pins the parameterised Cypher shape, one-hop Session
join, and poll_noise filter applied on the read side.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from factory.graph.runtime.adapters.neo4j_adapter import Neo4jGraph


class _FakeRecord:
    def __init__(self, data: dict) -> None:
        self._data = data

    def __getitem__(self, key: str):
        return self._data[key]

    def keys(self):
        return list(self._data.keys())

    def values(self):
        return list(self._data.values())

    def __iter__(self):
        return iter(self._data.items())

    def items(self):
        return self._data.items()


class _FakeCursor(list):
    def single(self):
        return self[0] if self else None


def _adapter_for_query(rows: list[dict]) -> tuple[Neo4jGraph, MagicMock]:
    adapter = Neo4jGraph()
    driver = MagicMock()
    session_ctx = MagicMock()
    session_ctx.__enter__.return_value = session_ctx
    session_ctx.__exit__.return_value = False
    session_ctx.run.return_value = _FakeCursor([_FakeRecord(r) for r in rows])
    driver.session.return_value = session_ctx
    adapter._driver = driver
    return adapter, session_ctx


class TestListRecentToolInvocationsCypher:
    """bd python-factory-c39g — query shape, params, schema."""

    def test_query_is_parameterised_and_one_hop_only(self) -> None:
        adapter, session = _adapter_for_query([
            {
                "tool_name": "agent_reason", "brick": "agent",
                "success": True, "latency_ms": 12,
                "created_at": "2026-05-12T12:00:00Z", "error": None,
                "workflow_run_id": "run-99",
                "args_summary": '{"task":"x"}', "caller": "ag_ui",
                "result_summary": '{"text":"ok"}',
                "invocation_session_id": None, "principal_id": None,
                "session_id": "session-42",
                "session_agent_id": "agent-red",
                "session_principal_id": "principal-7",
            },
        ])
        result = adapter.list_recent_tool_invocations(limit=100)
        called_cypher = session.run.call_args.args[0]
        kwargs = session.run.call_args.kwargs
        # Cypher uses parameters — no f-string interpolation of inputs.
        assert "$poll_noise" in called_cypher
        assert "$limit" in called_cypher
        assert "WHERE NOT t.tool_name IN $poll_noise" in called_cypher
        assert "ORDER BY t.created_at DESC" in called_cypher
        # One-hop Session join, no User/Agent traversal.
        assert "(s:Session)-[:CONTAINS_INVOCATION]->(t)" in called_cypher
        assert "(:User)" not in called_cypher
        assert "(:Agent)" not in called_cypher
        # Parameters bound, not interpolated.
        assert kwargs["limit"] == 100
        assert isinstance(kwargs["poll_noise"], list)
        # Row schema mirrors the networkx adapter.
        assert result.raw[0]["session_id"] == "session-42"
        assert result.raw[0]["session_agent_id"] == "agent-red"
        assert result.raw[0]["session_principal_id"] == "principal-7"

    def test_falls_back_to_invocation_session_id_when_session_missing(self) -> None:
        """When the OPTIONAL MATCH yields no Session, t.session_id wins."""
        adapter, _ = _adapter_for_query([
            {
                "tool_name": "agent_reason", "brick": "agent",
                "success": True, "latency_ms": 1,
                "created_at": "2026-05-12T12:00:00Z", "error": None,
                "workflow_run_id": "",
                "args_summary": None, "caller": None, "result_summary": None,
                "invocation_session_id": "fallback-sess",
                "principal_id": None,
                "session_id": None,
                "session_agent_id": None,
                "session_principal_id": None,
            },
        ])
        result = adapter.list_recent_tool_invocations(limit=10)
        assert result.raw[0]["session_id"] == "fallback-sess"
        # invocation_session_id is an internal alias and must be stripped.
        assert "invocation_session_id" not in result.raw[0]
