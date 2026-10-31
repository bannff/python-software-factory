"""Phase 4: per-game ``count_labels`` config override.

bd:python-factory-qer1z. Cites design verdicts:
  - meta-architect 9a4aba3c-d076-48a9-9499-5e24b0931a35
  - strands-expert  9b6d46cd-ed23-4a32-b3a0-40479b845768

Verifies ``DEFAULT_COUNT_LABELS`` keeps the security shape and the
``count_labels`` argument routes through ``_collect_findings``,
``graph_counts``, and ``build_findings_detail`` without touching the
SAST/DAST default.
"""
from __future__ import annotations

from factory.games.runtime import _rl_stages, workflow_report_graph
from factory.games.runtime._rl_stages import _collect_findings
from factory.games.runtime.workflow_report_findings import build_findings_detail
from factory.games.runtime.workflow_report_graph import graph_counts


class TestCountLabelsDefault:
    """``DEFAULT_COUNT_LABELS`` preserves the security shape."""

    def test_rl_stages_default_is_security_pair(self):
        assert _rl_stages.DEFAULT_COUNT_LABELS == ("Finding", "ProvenExploit")

    def test_workflow_report_graph_default_includes_security_quad(self):
        labels = workflow_report_graph.DEFAULT_COUNT_LABELS
        assert "Finding" in labels
        assert "ProvenExploit" in labels
        assert "SuspectedVuln" in labels
        assert "EndpointInventory" in labels


class TestCollectFindingsCountLabelsOverride:
    """``count_labels`` override drives ``_collect_findings`` per-domain."""

    def test_default_collects_finding_and_proven_exploit(self):
        calls: list[tuple[str, dict]] = []

        def invoker(name, **kw):
            calls.append((name, kw))
            if name == "graph_graph_get_findings_for_run":
                return {"rows": [{"id": "f-1"}], "count": 1}
            if name == "graph_graph_find_entities":
                return {"entities": [], "count": 0}
            raise AssertionError(name)

        _collect_findings(invoker, run_id="r1")
        names = [c[0] for c in calls]
        assert "graph_graph_get_findings_for_run" in names
        assert any(
            c[0] == "graph_graph_find_entities"
            and c[1]["entity_type"] == "ProvenExploit"
            for c in calls
        )

    def test_override_replaces_security_labels(self):
        calls: list[tuple[str, dict]] = []

        def invoker(name, **kw):
            calls.append((name, kw))
            return {"entities": [], "count": 0, "rows": []}

        _collect_findings(
            invoker, run_id="r1",
            count_labels=["WinePairing", "WorkoutLog"],
        )
        names = [c[0] for c in calls]
        # No "Finding" => no typed findings call.
        assert "graph_graph_get_findings_for_run" not in names
        types = sorted(
            c[1]["entity_type"]
            for c in calls if c[0] == "graph_graph_find_entities"
        )
        assert types == ["WinePairing", "WorkoutLog"]


class TestGraphCountsCountLabelsOverride:
    """``graph_counts`` forwards ``count_labels`` to the typed counter."""

    def test_default_uses_security_quad(self):
        captured = {}

        def invoker(name, **kw):
            captured.setdefault(name, kw)
            return {"counts": {}, "rows": [], "entities": []}

        graph_counts(invoker, run_id="r1")
        assert captured["graph_graph_count_entities_by_run"]["labels"] == [
            "SuspectedVuln", "Finding", "ProvenExploit", "EndpointInventory",
        ]

    def test_override_replaces_label_list(self):
        captured = {}

        def invoker(name, **kw):
            captured.setdefault(name, kw)
            return {"counts": {}, "rows": [], "entities": []}

        graph_counts(
            invoker, run_id="r1",
            count_labels=("WinePairing", "WorkoutLog"),
        )
        assert captured["graph_graph_count_entities_by_run"]["labels"] == [
            "WinePairing", "WorkoutLog",
        ]


class TestBuildFindingsDetailCountLabelsOverride:
    """``build_findings_detail`` overrides the exploit-label slot."""

    def _invoker(self, captured: list[dict]):
        def invoker(name, **kw):
            captured.append({"name": name, **kw})
            if name == "graph_graph_find_entities":
                return {"entities": [], "count": 0}
            if name == "graph_graph_get_findings_for_run":
                return {"rows": [], "count": 0}
            raise AssertionError(name)

        return invoker

    def test_default_pulls_proven_exploit(self):
        captured: list[dict] = []
        build_findings_detail(self._invoker(captured), run_id="r1")
        types = sorted(
            c["entity_type"] for c in captured
            if c["name"] == "graph_graph_find_entities"
        )
        assert types == ["ProvenExploit", "SuspectedVuln"]

    def test_override_replaces_exploit_label(self):
        captured: list[dict] = []
        build_findings_detail(
            self._invoker(captured), run_id="r1",
            count_labels=("Finding", "WineFlavorMatch"),
        )
        types = sorted(
            c["entity_type"] for c in captured
            if c["name"] == "graph_graph_find_entities"
        )
        # SuspectedVuln still queried (security column shape unchanged).
        assert types == ["SuspectedVuln", "WineFlavorMatch"]


class TestExplicitEmptyCountLabels:
    """Explicit empty label configuration performs no graph queries."""

    def test_collect_findings_returns_empty_without_queries(self):
        calls: list[tuple[str, dict]] = []
        assert _collect_findings(lambda name, **kw: calls.append((name, kw)), "r1", []) == []
        assert calls == []

    def test_graph_counts_returns_empty_without_queries(self):
        calls: list[tuple[str, dict]] = []
        result = graph_counts(lambda name, **kw: calls.append((name, kw)), "r1", [])
        assert result == {
            "suspected_vuln_count": 0,
            "finding_count": 0,
            "finding_verdicts": {},
            "proven_exploit_count": 0,
            "endpoints_discovered": 0,
        }
        assert calls == []

    def test_findings_detail_returns_empty_without_queries(self):
        calls: list[tuple[str, dict]] = []
        result = build_findings_detail(
            lambda name, **kw: calls.append((name, kw)), "r1", [],
        )
        assert result == {
            "findings": [],
            "finding_categories": {},
            "dynamic_verification_summary": {},
        }
        assert calls == []
