"""Edge-case coverage for typed run-scoped graph reads.

Companion to ``test_typed_runs_properties.py``. Pins the contract under
empty / unicode / oversize / negative inputs and locks the tenant
isolation guarantee for empty ``run_id`` filters: identity-bearing
helpers (``get_findings_for_run`` / ``count_entities_by_run`` /
``get_tool_invocations_for_run``) hard-no-match on empty ``run_id``;
``get_recent_findings`` keeps wildcard semantics for its OPTIONAL
filters (open-browse use case from the UI).

Adapter divergence + tenant-isolation gap was filed as bd
python-factory-j6uo (discovered-from j1lb). Networkx ``_matches``
treated empty as a wildcard while Neo4j binds ``f.run_id = $run_id``.
Fix landed under j6uo; the previous ``xfail`` is now a regular pass
and ``EXPECT_RUN_BLEED`` stays ``False`` as a tripwire.

Tracked under bd python-factory-j1lb / epic python-factory-kzd8.
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings, strategies as st

from factory.graph.runtime.adapters.networkx_adapter import NetworkXGraph
from factory.graph.runtime.ports import Entity

from ._typed_runs_fixtures import make_finding


# Tripwire: flip back to True only if a regression re-introduces the
# adapter-level bleed; bd python-factory-j6uo landed the fix.
EXPECT_RUN_BLEED = False


class TestEmptyResults:
    """Run-ids with no findings must return ``[]``, not raise."""

    def test_findings_for_unknown_run_returns_empty(self) -> None:
        graph = NetworkXGraph()
        graph.add_entity(make_finding("f1", "run-real"))
        result = graph.get_findings_for_run("run-does-not-exist")
        assert result.raw == []

    def test_recent_findings_no_data_returns_empty(self) -> None:
        result = NetworkXGraph().get_recent_findings()
        assert result.raw == []

    def test_count_unknown_label_returns_zero(self) -> None:
        graph = NetworkXGraph()
        graph.add_entity(make_finding("f1", "run-a"))
        counts = graph.count_entities_by_run("run-a", ["Bogus", "Finding"])
        assert counts == {"Bogus": 0, "Finding": 1}

    def test_target_app_not_found_returns_none(self) -> None:
        assert NetworkXGraph().get_target_app("missing-app") is None

    def test_tool_invocations_no_data_returns_empty(self) -> None:
        result = NetworkXGraph().get_tool_invocations_for_run("run-x")
        assert result.raw == []

    def test_finding_sast_fields_round_trip(self) -> None:
        """bd python-factory-ttq8: SAST code-evidence fields must project.

        Match_on for SAST is (cwe, file). If `file`/`function`/`line_*`/
        `agent_id`/`vuln_class` aren't in the projection allowlist, the
        scorer collapses every key to (cwe, None) and reports tp=0.
        """
        graph = NetworkXGraph()
        graph.add_entity(Entity(
            id="f-sast", type="Finding",
            properties={
                "id": "f-sast", "run_id": "run-a", "app": "myapp",
                "severity": "high", "cwe": "CWE-639",
                "file": "src/main/java/com/example/UserController.java",
                "function": "getUserById", "line_start": 42,
                "line_end": 58, "agent_id": "agent-sast-1",
                "vuln_class": "IDOR",
            },
        ))
        rows = graph.get_findings_for_run("run-a").raw
        assert len(rows) == 1
        row = rows[0]
        assert row["file"] == "src/main/java/com/example/UserController.java"
        assert row["function"] == "getUserById"
        assert row["line_start"] == 42
        assert row["line_end"] == 58
        assert row["agent_id"] == "agent-sast-1"
        assert row["vuln_class"] == "IDOR"


class TestLimits:
    """Limit clamping and oversize handling."""

    @given(limit=st.integers(min_value=-100, max_value=-1))
    @settings(max_examples=15, deadline=None)
    def test_negative_limit_clamps_to_zero(self, limit: int) -> None:
        graph = NetworkXGraph()
        for idx in range(3):
            graph.add_entity(make_finding(f"f-{idx}", "run-a"))
        rows = graph.get_findings_for_run("run-a", limit=limit).raw
        assert rows == []

    def test_very_large_limit_returns_all(self) -> None:
        graph = NetworkXGraph()
        for idx in range(7):
            graph.add_entity(make_finding(f"f-{idx}", "run-a"))
        rows = graph.get_findings_for_run("run-a", limit=10_000).raw
        assert len(rows) == 7

    def test_zero_limit_returns_empty(self) -> None:
        graph = NetworkXGraph()
        graph.add_entity(make_finding("f1", "run-a"))
        assert graph.get_findings_for_run("run-a", limit=0).raw == []


class TestUnicodeAndDuplicates:
    """Unicode keys and idempotent re-adds must not corrupt the graph."""

    @given(run_id=st.text(min_size=1, max_size=20,
                          alphabet=st.characters(
                              whitelist_categories=("L", "N"),
                              whitelist_characters="-_",
                          )))
    @settings(max_examples=20, deadline=None)
    def test_unicode_run_id_round_trip(self, run_id: str) -> None:
        graph = NetworkXGraph()
        graph.add_entity(make_finding("u-1", run_id))
        rows = graph.get_findings_for_run(run_id).raw
        assert len(rows) == 1
        assert rows[0]["run_id"] == run_id

    def test_unicode_in_title_preserved(self) -> None:
        graph = NetworkXGraph()
        graph.add_entity(Entity(
            id="f-emoji", type="Finding",
            properties={"id": "f-emoji", "run_id": "r1",
                        "title": "🔥 SQL injection (中文)",
                        "severity": "high"},
        ))
        row = graph.get_findings_for_run("r1").raw[0]
        assert row["title"] == "🔥 SQL injection (中文)"

    def test_duplicate_finding_id_is_idempotent(self) -> None:
        graph = NetworkXGraph()
        graph.add_entity(make_finding("f1", "run-a", severity="high"))
        graph.add_entity(make_finding("f1", "run-a", severity="critical"))
        rows = graph.get_findings_for_run("run-a").raw
        assert len(rows) == 1  # MERGE-by-id semantics
        assert rows[0]["severity"] == "critical"

    def test_count_dedups_by_node_id(self) -> None:
        graph = NetworkXGraph()
        graph.add_entity(make_finding("f1", "run-a"))
        graph.add_entity(make_finding("f1", "run-a"))  # same id, treated as MERGE
        counts = graph.count_entities_by_run("run-a", ["Finding"])
        assert counts["Finding"] == 1


class TestEmptyRunIdBleed:
    """Pin the bd j6uo divergence so a fix flips this from xfail to pass.

    NetworkX previously treated empty ``run_id`` as a wildcard; Neo4j
    did not. The j6uo fix makes networkx hard-no-match on empty
    ``run_id`` for identity-bearing helpers. This class is now the
    tripwire — broader isolation invariants live in the sibling file
    ``test_typed_runs_isolation.py``.
    """

    @pytest.mark.xfail(
        condition=EXPECT_RUN_BLEED, strict=True,
        reason="bd python-factory-j6uo: networkx empty run_id leaks all rows",
    )
    def test_empty_run_id_returns_empty_findings(self) -> None:
        graph = NetworkXGraph()
        graph.add_entity(make_finding("f1", "real-run"))
        graph.add_entity(make_finding("f2", "other-run"))
        rows = graph.get_findings_for_run("").raw
        assert rows == [], (
            f"empty run_id must not match-all (got {len(rows)} rows)"
        )

    def test_whitespace_run_id_does_not_match(self) -> None:
        """Sanity: non-empty whitespace doesn't accidentally hit anything."""
        graph = NetworkXGraph()
        graph.add_entity(make_finding("f1", "real-run"))
        rows = graph.get_findings_for_run("   ").raw
        assert rows == []
