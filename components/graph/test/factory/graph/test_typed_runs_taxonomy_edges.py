"""Property tests for the ``taxonomy_edges`` parameter.

Pins three contracts shipped under bd python-factory-ecph9 (epic
python-factory-hadbi domain-agnostic Companion-X):

1. **Default = back-compat.** ``taxonomy_edges=None`` keeps the legacy
   security CWE/OCSF row keys (``cwe_id``, ``cwe_name``, ``ocsf_class``,
   ``ocsf_uid``) — security callers don't change.
2. **Domain agnostic.** Caller-supplied edges produce the columns the
   caller declared. A hypothetical wine domain passing ``TASTED_AS``
   gets ``varietal_id`` / ``varietal_name`` rows, no CWE columns.
3. **Empty list = no taxonomy join.** ``taxonomy_edges=[]`` produces
   rows that do NOT contain any of the legacy CWE/OCSF columns.

Both ``get_findings_for_run`` and ``get_recent_findings`` are covered.
``TaxonomyEdgeSpec`` validation lives in ``test_taxonomy_edge_spec.py``.
"""

from __future__ import annotations

from factory.graph.runtime.adapters.networkx_adapter import NetworkXGraph
from factory.graph.runtime.models import TaxonomyEdgeSpec
from factory.graph.runtime.ports import Entity, Relationship

from ._typed_runs_fixtures import make_finding


# Legacy security default row columns — must round-trip when
# ``taxonomy_edges is None`` and must NOT appear when the caller passes
# an empty list or a non-overlapping edge set.
_LEGACY_SECURITY_KEYS = ("cwe_id", "cwe_name", "ocsf_class", "ocsf_uid")


def _seed_security_finding(graph: NetworkXGraph, fid: str = "f-1") -> None:
    """Wire a Finding linked to a CWECategory + OCSFEventClass."""
    graph.add_entity(make_finding(fid, "run-a", app="myapp"))
    graph.add_entity(Entity(
        id="cwe-639", type="CWECategory",
        properties={"cwe_id": "CWE-639", "name": "Authorization Bypass"},
    ))
    graph.add_entity(Entity(
        id="ocsf-2001", type="OCSFEventClass",
        properties={"class_uid": 2001, "class_name": "Security Finding"},
    ))
    graph.add_relationship(Relationship(
        id="r-cwe", type="CLASSIFIED_AS",
        source_id=fid, target_id="cwe-639",
    ))
    graph.add_relationship(Relationship(
        id="r-ocsf", type="CONFORMS_TO",
        source_id=fid, target_id="ocsf-2001",
    ))


def _wine_finding_with_varietal(
    graph: NetworkXGraph, fid: str = "f-1",
) -> None:
    graph.add_entity(make_finding(fid, "run-a"))
    graph.add_entity(Entity(
        id="varietal-1", type="Varietal",
        properties={"id": "v-1", "name": "Pinot Noir"},
    ))
    graph.add_relationship(Relationship(
        id="r-tasted", type="TASTED_AS",
        source_id=fid, target_id="varietal-1",
    ))


_WINE_EDGES = [
    TaxonomyEdgeSpec(
        relationship_type="TASTED_AS", target_label="Varietal",
        target_props={"id": "varietal_id", "name": "varietal_name"},
    ),
]


class TestDefaultBackwardCompat:
    """``taxonomy_edges=None`` preserves legacy security row keys."""

    def test_findings_for_run_default_keeps_security_keys(self) -> None:
        graph = NetworkXGraph()
        _seed_security_finding(graph)
        rows = list(graph.get_findings_for_run("run-a").raw or [])
        assert len(rows) == 1
        for key in _LEGACY_SECURITY_KEYS:
            assert key in rows[0], f"missing legacy column: {key}"
        assert rows[0]["cwe_id"] == "CWE-639"
        assert rows[0]["cwe_name"] == "Authorization Bypass"
        assert rows[0]["ocsf_uid"] == 2001
        assert rows[0]["ocsf_class"] == "Security Finding"

    def test_recent_findings_default_keeps_security_keys(self) -> None:
        graph = NetworkXGraph()
        _seed_security_finding(graph)
        rows = list(graph.get_recent_findings(run_id="run-a").raw or [])
        assert len(rows) == 1
        for key in _LEGACY_SECURITY_KEYS:
            assert key in rows[0]
        assert rows[0]["cwe_id"] == "CWE-639"
        assert rows[0]["ocsf_class"] == "Security Finding"

    def test_findings_with_no_taxonomy_neighbors_get_none_columns(self) -> None:
        """Default columns appear with ``None`` when neighbors are missing."""
        graph = NetworkXGraph()
        graph.add_entity(make_finding("f-1", "run-a"))  # no CWE/OCSF edges
        row = list(graph.get_findings_for_run("run-a").raw or [])[0]
        for key in _LEGACY_SECURITY_KEYS:
            assert key in row
            assert row[key] is None


class TestDomainAgnosticEdges:
    """Caller-supplied edges produce caller-declared row columns."""

    def test_wine_domain_edges_produce_varietal_columns(self) -> None:
        graph = NetworkXGraph()
        _wine_finding_with_varietal(graph)
        rows = list(graph.get_findings_for_run(
            "run-a", taxonomy_edges=_WINE_EDGES,
        ).raw or [])
        assert len(rows) == 1
        assert rows[0]["varietal_id"] == "v-1"
        assert rows[0]["varietal_name"] == "Pinot Noir"
        # Legacy security columns are NOT present (no leak).
        for key in _LEGACY_SECURITY_KEYS:
            assert key not in rows[0], f"unexpected leak: {key}"

    def test_caller_edges_with_no_match_produce_none_columns(self) -> None:
        """Declared columns surface as ``None`` when the edge is missing."""
        graph = NetworkXGraph()
        graph.add_entity(make_finding("f-1", "run-a"))
        rows = list(graph.get_findings_for_run(
            "run-a", taxonomy_edges=_WINE_EDGES,
        ).raw or [])
        assert rows[0]["varietal_id"] is None
        assert rows[0]["varietal_name"] is None
        for key in _LEGACY_SECURITY_KEYS:
            assert key not in rows[0]

    def test_recent_findings_honors_caller_edges(self) -> None:
        graph = NetworkXGraph()
        _wine_finding_with_varietal(graph)
        rows = list(graph.get_recent_findings(
            run_id="run-a", taxonomy_edges=_WINE_EDGES,
        ).raw or [])
        assert rows[0]["varietal_id"] == "v-1"
        for key in _LEGACY_SECURITY_KEYS:
            assert key not in rows[0]


class TestEmptyEdgesList:
    """``taxonomy_edges=[]`` means: no taxonomy columns in the output."""

    def test_empty_edges_omit_security_columns_findings_for_run(self) -> None:
        graph = NetworkXGraph()
        _seed_security_finding(graph)  # CWE/OCSF wired up, but...
        rows = list(graph.get_findings_for_run(
            "run-a", taxonomy_edges=[],
        ).raw or [])
        assert len(rows) == 1
        # Caller asked for zero taxonomy joins, so no taxonomy columns.
        for key in _LEGACY_SECURITY_KEYS:
            assert key not in rows[0]
        # But the Finding scalar props still round-trip.
        assert rows[0]["id"] == "f-1"
        assert rows[0]["app"] == "myapp"
        assert rows[0]["run_id"] == "run-a"

    def test_empty_edges_omit_security_columns_recent_findings(self) -> None:
        graph = NetworkXGraph()
        _seed_security_finding(graph)
        rows = list(graph.get_recent_findings(
            run_id="run-a", taxonomy_edges=[],
        ).raw or [])
        for key in _LEGACY_SECURITY_KEYS:
            assert key not in rows[0]


# Human-as-labeler grade columns (depth slice 2, bd tz8hi). Neutral,
# domain-agnostic; projected by both adapters so a graded finding survives
# the typed re-read the games/RL loop consumes.
_HUMAN_GRADE_KEYS = ("human_verdict", "graded_by", "graded_at", "graded_source")


class TestHumanGradeColumns:
    """The human-grade props round-trip through the fixed Finding projection."""

    def test_graded_finding_projects_human_verdict(self) -> None:
        graph = NetworkXGraph()
        graph.add_entity(Entity(
            id="f-1", type="Finding",
            properties={
                "id": "f-1", "run_id": "run-a", "title": "SQLi",
                "human_verdict": "agree", "graded_by": "kiro-agent",
                "graded_at": "2026-06-08T00:00:00Z", "graded_source": "ide",
            },
        ))
        row = list(graph.get_findings_for_run("run-a").raw or [])[0]
        assert row["human_verdict"] == "agree"
        assert row["graded_by"] == "kiro-agent"
        assert row["graded_at"] == "2026-06-08T00:00:00Z"
        assert row["graded_source"] == "ide"

    def test_ungraded_finding_has_none_grade_columns(self) -> None:
        graph = NetworkXGraph()
        graph.add_entity(make_finding("f-1", "run-a"))
        row = list(graph.get_findings_for_run("run-a").raw or [])[0]
        for key in _HUMAN_GRADE_KEYS:
            assert key in row, f"missing grade column: {key}"
            assert row[key] is None
