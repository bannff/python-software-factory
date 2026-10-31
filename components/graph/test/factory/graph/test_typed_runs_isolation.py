"""Tenant-isolation tests for run-scoped typed graph reads.

Sibling to ``test_typed_runs_edge_cases.py``. Locks the j6uo contract:
identity-bearing helpers (``get_findings_for_run`` /
``count_entities_by_run`` / ``get_tool_invocations_for_run``)
hard-no-match on empty ``run_id``; ``get_recent_findings`` keeps its
wildcard semantics for OPTIONAL filters (the open-browse case).

Also includes a Hypothesis property: any two distinct non-empty
``run_id`` values partition findings disjointly. This is the formal
shape of "no cross-run bleed".

Tracked under bd python-factory-j6uo / epic python-factory-kzd8.
"""

from __future__ import annotations

from hypothesis import given, settings, strategies as st

from factory.graph.runtime.adapters.networkx_adapter import NetworkXGraph
from factory.graph.runtime.ports import Entity

from ._typed_runs_fixtures import make_finding


_RUN_ID_ALPHA = st.characters(
    whitelist_categories=("L", "N"),
    whitelist_characters="-_",
)
_RUN_ID = st.text(min_size=1, max_size=12, alphabet=_RUN_ID_ALPHA)


class TestEmptyRunIdIsolation:
    """Identity-bearing helpers must reject empty ``run_id``."""

    def test_count_entities_by_run_empty_zeros_all_labels(self) -> None:
        graph = NetworkXGraph()
        graph.add_entity(make_finding("f1", "run-a"))
        graph.add_entity(Entity(
            id="bogus-1", type="Bogus", properties={"run_id": "run-a"},
        ))
        counts = graph.count_entities_by_run("", ["Finding", "Bogus"])
        assert counts == {"Finding": 0, "Bogus": 0}

    def test_tool_invocations_empty_run_id_returns_empty(self) -> None:
        graph = NetworkXGraph()
        graph.add_entity(Entity(
            id="inv-1", type="ToolInvocation",
            properties={"workflow_run_id": "run-a", "sequence": 0,
                        "tool_name": "x"},
        ))
        assert graph.get_tool_invocations_for_run("").raw == []

    def test_findings_for_run_with_app_filter_empty_run_id(self) -> None:
        """Even with an app filter, empty ``run_id`` hard-no-matches."""
        graph = NetworkXGraph()
        graph.add_entity(make_finding("f1", "run-a", app="webapp"))
        assert graph.get_findings_for_run("", app="webapp").raw == []


class TestRecentFindingsOpenBrowse:
    """``get_recent_findings`` preserves wildcard ('no filter') semantics."""

    def test_recent_findings_empty_run_id_is_no_filter(self) -> None:
        graph = NetworkXGraph()
        graph.add_entity(make_finding("f1", "run-a"))
        graph.add_entity(make_finding("f2", "run-b"))
        rows = graph.get_recent_findings(run_id="").raw
        assert {r["id"] for r in rows} == {"f1", "f2"}

    def test_recent_findings_severity_filter_still_works(self) -> None:
        graph = NetworkXGraph()
        graph.add_entity(make_finding("f1", "run-a", severity="critical"))
        graph.add_entity(make_finding("f2", "run-b", severity="low"))
        rows = graph.get_recent_findings(severity="critical", run_id="").raw
        assert {r["id"] for r in rows} == {"f1"}

    def test_recent_findings_app_filter_still_works(self) -> None:
        graph = NetworkXGraph()
        graph.add_entity(make_finding("f1", "run-a", app="webapp"))
        graph.add_entity(make_finding("f2", "run-b", app="api"))
        rows = graph.get_recent_findings(app="webapp", run_id="").raw
        assert {r["id"] for r in rows} == {"f1"}

    def test_recent_findings_projects_sast_evidence_fields(self) -> None:
        """bd python-factory-ttq8: open-browse path also needs the fields."""
        graph = NetworkXGraph()
        graph.add_entity(Entity(
            id="f-rec", type="Finding",
            properties={
                "id": "f-rec", "run_id": "run-a", "severity": "high",
                "cwe": "CWE-639", "file": "foo.java",
                "function": "fn", "line_start": 5, "line_end": 9,
                "agent_id": "agent-rec", "vuln_class": "IDOR",
            },
        ))
        row = graph.get_recent_findings().raw[0]
        for key in ("file", "function", "line_start", "line_end",
                    "agent_id", "vuln_class"):
            assert key in row, f"missing {key} in get_recent_findings"
        assert row["file"] == "foo.java"


class TestRunPartitionProperty:
    """Property: distinct non-empty ``run_id`` values never bleed."""

    @given(run_id_a=_RUN_ID, run_id_b=_RUN_ID)
    @settings(max_examples=40, deadline=None)
    def test_distinct_run_ids_partition_disjointly(
        self, run_id_a: str, run_id_b: str,
    ) -> None:
        if run_id_a == run_id_b:
            return  # property is conditional on a != b
        graph = NetworkXGraph()
        graph.add_entity(make_finding("f-a", run_id_a))
        graph.add_entity(make_finding("f-b", run_id_b))
        ids_a = {r["id"] for r in graph.get_findings_for_run(run_id_a).raw}
        ids_b = {r["id"] for r in graph.get_findings_for_run(run_id_b).raw}
        assert ids_a == {"f-a"}
        assert ids_b == {"f-b"}
        assert ids_a.isdisjoint(ids_b)
