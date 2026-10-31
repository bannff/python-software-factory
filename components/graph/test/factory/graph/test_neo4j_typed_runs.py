"""Tests for Neo4j adapter run-scoped typed reads (mocked driver).

Verifies that the Neo4j adapter implements the same ``KnowledgeGraph``
Protocol surface as networkx — i.e. dialect equivalence in shape — and
that each typed read emits a parametrised Cypher query (no string
interpolation of user input).

Tracked under bd python-factory-j1lb / epic python-factory-kzd8.
"""

from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import MagicMock

import pytest

from factory.graph.runtime.adapters.neo4j_adapter import Neo4jGraph


@contextmanager
def _mock_session(rows: list[dict]):
    """Yield a fake session whose run() returns the given rows."""
    session = MagicMock()
    session.__enter__ = lambda self: self
    session.__exit__ = lambda *args: None
    cursor = MagicMock()
    cursor.__iter__ = lambda self: iter([MagicMock(**{
        "__getitem__": lambda _, k: row[k],
        "data": lambda: row,
        "keys": lambda: list(row.keys()),
    }) for row in rows])
    cursor.single.return_value = (
        MagicMock(__getitem__=lambda _, k: rows[0][k]) if rows else None
    )
    session.run.return_value = cursor
    yield session


def _adapter_with_rows(rows: list[dict]) -> tuple[Neo4jGraph, MagicMock]:
    adapter = Neo4jGraph()
    driver = MagicMock()
    session_ctx = MagicMock()
    session_ctx.__enter__.return_value = session_ctx
    session_ctx.__exit__.return_value = False
    cursor = [_FakeRecord(r) for r in rows]
    session_ctx.run.return_value = cursor
    cursor_single = _FakeRecord(rows[0]) if rows else None
    session_ctx.run.return_value.single = lambda: cursor_single
    driver.session.return_value = session_ctx
    adapter._driver = driver
    return adapter, session_ctx


class _FakeRecord:
    """Minimal stand-in for a neo4j Record."""

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
    """List that also exposes single() for cursor-shaped reads."""

    def single(self):
        return self[0] if self else None


def _adapter_for_query(rows: list[dict]) -> tuple[Neo4jGraph, MagicMock]:
    """Wire up an adapter whose driver returns the given rows."""
    adapter = Neo4jGraph()
    driver = MagicMock()
    session_ctx = MagicMock()
    session_ctx.__enter__.return_value = session_ctx
    session_ctx.__exit__.return_value = False
    session_ctx.run.return_value = _FakeCursor([_FakeRecord(r) for r in rows])
    driver.session.return_value = session_ctx
    adapter._driver = driver
    return adapter, session_ctx


class TestNeo4jTypedReads:
    """Each typed read emits parameterised Cypher and shapes results."""

    def test_get_findings_for_run_uses_parameters(self) -> None:
        adapter, session = _adapter_for_query([
            {
                "id": "f1", "title": "x", "description": "",
                "severity": "high", "location": "", "remediation": "",
                "cwe": "", "evidence": "", "verdict": "",
                "run_id": "r1", "app": "a1",
                "affected_resource_arn": "", "finding_type": "",
                "category": "", "created_at": "2026-01-01T00:00:00Z",
                "file": "src/main/java/Foo.java", "function": "doIt",
                "line_start": 12, "line_end": 18, "agent_id": "agent-x",
                "vuln_class": "IDOR",
                "cwe_id": "CWE-79", "cwe_name": "XSS",
                "ocsf_class": "Security Finding", "ocsf_uid": 2001,
            },
        ])
        result = adapter.get_findings_for_run("r1", app="a1", limit=10)
        assert len(result.raw) == 1
        assert result.raw[0]["id"] == "f1"
        assert result.raw[0]["cwe_id"] == "CWE-79"
        # bd python-factory-ttq8: SAST scorer match_on=(cwe,file) needs
        # these projected — collapse to None broke f1 in live smoke.
        assert result.raw[0]["file"] == "src/main/java/Foo.java"
        assert result.raw[0]["function"] == "doIt"
        assert result.raw[0]["line_start"] == 12
        assert result.raw[0]["line_end"] == 18
        assert result.raw[0]["agent_id"] == "agent-x"
        assert result.raw[0]["vuln_class"] == "IDOR"
        # Cypher parameters were bound — not interpolated.
        called_cypher = session.run.call_args.args[0]
        kwargs = session.run.call_args.kwargs
        assert "$run_id" in called_cypher
        assert "$app" in called_cypher
        assert "$limit" in called_cypher
        # bd ttq8: assert each new field is in the RETURN projection.
        for field in ("f.file AS file", "f.function AS function",
                      "f.line_start AS line_start", "f.line_end AS line_end",
                      "f.agent_id AS agent_id",
                      "f.vuln_class AS vuln_class"):
            assert field in called_cypher, f"missing projection: {field}"
        assert kwargs["run_id"] == "r1"
        assert kwargs["app"] == "a1"

    def test_count_entities_by_run_sanitises_label(self) -> None:
        adapter, session = _adapter_for_query([{"c": 7}])
        # Inject a malicious label — must be stripped to bare alphanumerics.
        counts = adapter.count_entities_by_run(
            "r1", ["Finding; DROP DATABASE"],
        )
        assert "Finding; DROP DATABASE" in counts
        called_cypher = session.run.call_args.args[0]
        # The dangerous chars must have been stripped from the rendered label.
        assert ";" not in called_cypher
        assert "DROP" in called_cypher  # alphanumeric only — DROP keyword survives stripping
        # but the run_id is still passed as a parameter, not interpolated.
        assert "$run_id" in called_cypher

    def test_get_recent_findings_omits_filters_when_empty(self) -> None:
        adapter, session = _adapter_for_query([])
        adapter.get_recent_findings(limit=10)
        called_cypher = session.run.call_args.args[0]
        # No WHERE clause when severity/app/run_id are all empty.
        assert "WHERE" not in called_cypher
        assert "ORDER BY f.created_at DESC" in called_cypher

    def test_get_recent_findings_combines_filters(self) -> None:
        adapter, session = _adapter_for_query([])
        adapter.get_recent_findings(severity="high", app="a", run_id="r")
        called_cypher = session.run.call_args.args[0]
        kwargs = session.run.call_args.kwargs
        assert "f.severity = $severity" in called_cypher
        assert "f.app = $app" in called_cypher
        assert "f.run_id = $run_id" in called_cypher
        assert kwargs == {
            "limit": 50, "severity": "high", "app": "a", "run_id": "r",
        }

    def test_get_target_app_with_run_id_tiebreaker(self) -> None:
        adapter, session = _adapter_for_query([{"id": "app-x"}])
        # Pre-stage get_entity to return None so we don't recurse on driver.
        adapter.get_entity = MagicMock(return_value=None)
        adapter.get_target_app("x", run_id="r1")
        called_cypher = session.run.call_args.args[0]
        assert "n.app = $app OR n.name = $app" in called_cypher
        assert "n.last_recon_run_id = $run_id" in called_cypher

    def test_get_tool_invocations_emits_ordered_query(self) -> None:
        adapter, session = _adapter_for_query([
            {"t": {"id": "inv-1", "properties": {"sequence": 0}}},
            {"t": {"id": "inv-2", "properties": {"sequence": 1}}},
        ])
        result = adapter.get_tool_invocations_for_run("r1", limit=5)
        called_cypher = session.run.call_args.args[0]
        assert "t.workflow_run_id = $run_id" in called_cypher
        assert "ORDER BY t.sequence ASC" in called_cypher
        assert len(result.raw) == 2
        assert result.raw[0]["id"] == "inv-1"
