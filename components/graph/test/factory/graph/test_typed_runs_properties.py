"""Property tests for typed run-scoped graph tools (round-trip + invariants).

Covers the 6 ``KnowledgeGraph`` Protocol methods that replace the
Cypher escape hatch on the networkx adapter (bd python-factory-j1lb /
epic python-factory-kzd8) plus ``list_recent_tool_invocations``
(bd python-factory-c39g). Stateful run-scoping invariants live in
``test_typed_runs_state_machine.py``.
"""

from __future__ import annotations

from hypothesis import given, strategies as st

from factory.graph.runtime.adapters.networkx_adapter import NetworkXGraph
from factory.graph.runtime.ports import Entity

from ._typed_runs_fixtures import (
    SETTINGS, apps, created_at, make_finding, run_ids, severities,
)


class TestTypedRunReads:
    """Round-trip + filter + sort + limit invariants for each tool."""

    @given(run_id=run_ids, app=apps, severity=severities, created=created_at)
    @SETTINGS
    def test_findings_for_run_round_trip(
        self, run_id: str, app: str, severity: str, created: str,
    ) -> None:
        graph = NetworkXGraph()
        finding = make_finding(
            "finding-1", run_id, app=app, severity=severity, created=created,
        )
        # bd python-factory-ttq8: pin SAST code-evidence fields.
        finding.properties.update({
            "file": "src/main/java/Foo.java", "function": "doIt",
            "line_start": 12, "line_end": 18,
            "agent_id": "agent-x", "vuln_class": "IDOR",
        })
        graph.add_entity(finding)
        rows = list(graph.get_findings_for_run(run_id, app=app, limit=10).raw or [])
        assert len(rows) == 1
        assert rows[0]["id"] == "finding-1"
        assert rows[0]["run_id"] == run_id
        assert rows[0]["app"] == app
        assert rows[0]["severity"] == severity
        for key in ("cwe_id", "cwe_name", "ocsf_class", "ocsf_uid"):
            assert key in rows[0]
        # bd ttq8: SAST scorer match_on=(cwe,file) — these must round-trip.
        assert rows[0]["file"] == "src/main/java/Foo.java"
        assert rows[0]["function"] == "doIt"
        assert rows[0]["line_start"] == 12
        assert rows[0]["line_end"] == 18
        assert rows[0]["agent_id"] == "agent-x"
        assert rows[0]["vuln_class"] == "IDOR"

    @given(other=run_ids)
    @SETTINGS
    def test_findings_for_run_filters_run_id(self, other: str) -> None:
        graph = NetworkXGraph()
        graph.add_entity(make_finding("f-keep", "run-a"))
        graph.add_entity(make_finding("f-drop", other))
        rows = list(graph.get_findings_for_run("run-a").raw or [])
        for row in rows:
            assert row["run_id"] == "run-a"

    @given(limit=st.integers(min_value=0, max_value=5),
           extras=st.integers(min_value=0, max_value=8))
    @SETTINGS
    def test_findings_for_run_respects_limit(
        self, limit: int, extras: int,
    ) -> None:
        graph = NetworkXGraph()
        for idx in range(extras):
            graph.add_entity(make_finding(f"f-{idx}", "run-a"))
        rows = list(graph.get_findings_for_run("run-a", limit=limit).raw or [])
        assert len(rows) <= limit

    @given(seqs=st.lists(created_at, min_size=2, max_size=10, unique=True))
    @SETTINGS
    def test_recent_findings_sorted_desc(self, seqs: list[str]) -> None:
        graph = NetworkXGraph()
        for idx, ts in enumerate(seqs):
            graph.add_entity(make_finding(f"f-{idx}", "run-a", created=ts))
        rows = list(graph.get_recent_findings(limit=len(seqs)).raw or [])
        timestamps = [str(r.get("created_at", "")) for r in rows]
        assert timestamps == sorted(timestamps, reverse=True)

    @given(severity=severities, run_id=run_ids)
    @SETTINGS
    def test_recent_findings_filters(self, severity: str, run_id: str) -> None:
        graph = NetworkXGraph()
        graph.add_entity(make_finding("f-match", run_id, severity=severity))
        graph.add_entity(make_finding(
            "f-other", "run-z",
            severity="info" if severity != "info" else "low",
        ))
        rows = list(graph.get_recent_findings(
            severity=severity, run_id=run_id,
        ).raw or [])
        for row in rows:
            assert row["severity"] == severity
            assert row["run_id"] == run_id

    @given(labels=st.lists(
        st.sampled_from([
            "SuspectedVuln", "Finding", "ProvenExploit",
            "EndpointInventory", "TargetApp",
        ]),
        min_size=1, max_size=4, unique=True,
    ))
    @SETTINGS
    def test_count_entities_by_run_partitions(self, labels: list[str]) -> None:
        graph = NetworkXGraph()
        for idx, label in enumerate(labels):
            for run_id in ("run-a", "run-b"):
                graph.add_entity(Entity(
                    id=f"{label.lower()}-{idx}-{run_id}",
                    type=label, properties={"run_id": run_id},
                ))
        counts = graph.count_entities_by_run("run-a", labels)
        assert set(counts.keys()) == set(labels)
        for label in labels:
            assert counts[label] == 1

    @given(target_app=apps, run_id=run_ids)
    @SETTINGS
    def test_get_target_app_singleton(
        self, target_app: str, run_id: str,
    ) -> None:
        graph = NetworkXGraph()
        graph.add_entity(Entity(
            id=f"app-{target_app}", type="TargetApp",
            properties={
                "app": target_app, "name": target_app,
                "last_recon_run_id": run_id,
                "created_at": "2026-01-01T00:00:00Z",
            },
        ))
        graph.add_entity(Entity(
            id="app-other", type="TargetApp",
            properties={"app": "other", "name": "other",
                        "created_at": "2026-01-01T00:00:01Z"},
        ))
        result = graph.get_target_app(target_app, run_id=run_id)
        assert result is not None
        assert (
            result.properties.get("app") == target_app
            or result.properties.get("name") == target_app
        )

    @given(seq=st.lists(
        st.integers(min_value=0, max_value=99),
        min_size=2, max_size=8, unique=True,
    ))
    @SETTINGS
    def test_tool_invocations_ordered_ascending(self, seq: list[int]) -> None:
        graph = NetworkXGraph()
        for n in seq:
            graph.add_entity(Entity(
                id=f"inv-{n}", type="ToolInvocation",
                properties={
                    "workflow_run_id": "run-a", "sequence": n,
                    "tool_name": f"tool-{n}",
                },
            ))
        rows = list(graph.get_tool_invocations_for_run(
            "run-a", limit=len(seq),
        ).raw or [])
        sequences = [int(r.get("sequence", -1)) for r in rows]
        assert sequences == sorted(sequences)
# End of typed run property tests.