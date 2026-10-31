"""Cypher-shape tests for ``taxonomy_edges`` on the Neo4j adapter.

Pins three contracts shipped under bd python-factory-ecph9 (epic
python-factory-hadbi):

1. ``taxonomy_edges=None`` builds Cypher with the legacy CWE/OCSF
   OPTIONAL MATCH + projections — security callers are byte-identical.
2. Caller-supplied edges build OPTIONAL MATCH + projection clauses
   from the spec — no CWE/OCSF labels appear in Cypher.
3. ``taxonomy_edges=[]`` emits Cypher with NO OPTIONAL MATCH and only
   the base Finding projections.
4. ``relationship_type`` / ``target_label`` / column names are sanitised
   to bare alphanumerics (Cypher labels can't be parameterised).
"""

from __future__ import annotations

from unittest.mock import MagicMock

from factory.graph.runtime.adapters.neo4j_adapter import Neo4jGraph
from factory.graph.runtime.models import TaxonomyEdgeSpec


class _FakeRecord:
    def __init__(self, data: dict) -> None:
        self._data = data

    def __getitem__(self, key: str):
        return self._data[key]

    def keys(self):
        return list(self._data.keys())

    def items(self):
        return self._data.items()

    def __iter__(self):
        return iter(self._data.items())


class _FakeCursor(list):
    def single(self):
        return self[0] if self else None


def _adapter(rows: list[dict]) -> tuple[Neo4jGraph, MagicMock]:
    adapter = Neo4jGraph()
    driver = MagicMock()
    session_ctx = MagicMock()
    session_ctx.__enter__.return_value = session_ctx
    session_ctx.__exit__.return_value = False
    session_ctx.run.return_value = _FakeCursor([_FakeRecord(r) for r in rows])
    driver.session.return_value = session_ctx
    adapter._driver = driver
    return adapter, session_ctx


class TestDefaultEdges:
    """``taxonomy_edges=None`` keeps the legacy CWE/OCSF Cypher shape."""

    def test_default_cypher_walks_classified_as_and_conforms_to(self) -> None:
        adapter, session = _adapter([])
        adapter.get_findings_for_run("r1", app="a", limit=10)
        cypher = session.run.call_args.args[0]
        assert "OPTIONAL MATCH (f)-[:CLASSIFIED_AS]->" in cypher
        assert "CWECategory" in cypher
        assert "OPTIONAL MATCH (f)-[:CONFORMS_TO]->" in cypher
        assert "OCSFEventClass" in cypher
        # Legacy projections preserved verbatim — security tests must pass.
        assert " AS cwe_id" in cypher
        assert " AS cwe_name" in cypher
        assert " AS ocsf_uid" in cypher
        assert " AS ocsf_class" in cypher

    def test_default_cypher_on_recent_findings(self) -> None:
        adapter, session = _adapter([])
        adapter.get_recent_findings(severity="high", limit=10)
        cypher = session.run.call_args.args[0]
        assert "OPTIONAL MATCH (f)-[:CLASSIFIED_AS]->" in cypher
        assert "OPTIONAL MATCH (f)-[:CONFORMS_TO]->" in cypher


class TestCallerSuppliedEdges:
    """Caller edges produce caller-declared OPTIONAL MATCH + projections."""

    def test_wine_edges_build_tasted_as_cypher(self) -> None:
        adapter, session = _adapter([])
        wine_edges = [
            TaxonomyEdgeSpec(
                relationship_type="TASTED_AS", target_label="Varietal",
                target_props={"id": "varietal_id", "name": "varietal_name"},
            ),
        ]
        adapter.get_findings_for_run(
            "r1", app="", limit=10, taxonomy_edges=wine_edges,
        )
        cypher = session.run.call_args.args[0]
        assert "OPTIONAL MATCH (f)-[:TASTED_AS]->" in cypher
        assert "Varietal" in cypher
        assert " AS varietal_id" in cypher
        assert " AS varietal_name" in cypher
        # No legacy security labels leaked.
        assert "CLASSIFIED_AS" not in cypher
        assert "CWECategory" not in cypher
        assert "CONFORMS_TO" not in cypher
        assert "OCSFEventClass" not in cypher

    def test_recent_findings_with_caller_edges(self) -> None:
        adapter, session = _adapter([])
        edges = [
            TaxonomyEdgeSpec(
                relationship_type="LINKED_TO", target_label="Foo",
                target_props={"x": "foo_x"},
            ),
        ]
        adapter.get_recent_findings(
            severity="", app="", run_id="r1", limit=10, taxonomy_edges=edges,
        )
        cypher = session.run.call_args.args[0]
        assert "OPTIONAL MATCH (f)-[:LINKED_TO]->" in cypher
        assert " AS foo_x" in cypher
        assert "CLASSIFIED_AS" not in cypher


class TestEmptyEdges:
    """``taxonomy_edges=[]`` emits no OPTIONAL MATCH and only base columns."""

    def test_empty_edges_emit_no_optional_match(self) -> None:
        adapter, session = _adapter([])
        adapter.get_findings_for_run(
            "r1", app="", limit=10, taxonomy_edges=[],
        )
        cypher = session.run.call_args.args[0]
        assert "OPTIONAL MATCH" not in cypher
        assert "CWECategory" not in cypher
        assert "OCSFEventClass" not in cypher
        # Base scalar projections still present.
        assert " AS id" in cypher
        assert " AS run_id" in cypher
        assert " AS severity" in cypher

    def test_empty_edges_recent_findings(self) -> None:
        adapter, session = _adapter([])
        adapter.get_recent_findings(limit=5, taxonomy_edges=[])
        cypher = session.run.call_args.args[0]
        assert "OPTIONAL MATCH" not in cypher


class TestCypherSanitisation:
    """Edge fields are sanitised to bare alphanumerics."""

    def test_dangerous_relationship_type_is_stripped(self) -> None:
        adapter, session = _adapter([])
        edges = [
            TaxonomyEdgeSpec(
                relationship_type="X; DROP DATABASE",
                target_label="Foo",
                target_props={"a": "col_a"},
            ),
        ]
        adapter.get_findings_for_run(
            "r1", app="", limit=10, taxonomy_edges=edges,
        )
        cypher = session.run.call_args.args[0]
        # ; and whitespace stripped — DROP+DATABASE survive but they
        # land inside a relationship-type position so they are
        # syntactically a label, not a statement.
        assert ";" not in cypher
        assert "OPTIONAL MATCH" in cypher

    def test_dangerous_column_name_is_stripped(self) -> None:
        adapter, session = _adapter([])
        edges = [
            TaxonomyEdgeSpec(
                relationship_type="REL", target_label="Foo",
                target_props={"a": "col; DROP"},
            ),
        ]
        adapter.get_findings_for_run(
            "r1", app="", limit=10, taxonomy_edges=edges,
        )
        cypher = session.run.call_args.args[0]
        assert ";" not in cypher
