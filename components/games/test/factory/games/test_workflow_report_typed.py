"""Pin workflow_report findings + graph writers to typed graph tools.

Tracked under bd python-factory-ky0i / epic python-factory-kzd8.
Target-app delegation lives in ``test_workflow_report_target_typed.py``.
"""
from __future__ import annotations

import pathlib
from typing import Any

from hypothesis import given, settings, strategies as st

from factory.games.runtime.workflow_report_findings import build_findings_detail
from types import SimpleNamespace
from factory.games.runtime.workflow_report_graph import graph_counts
from factory.graph.mcp.core_models import EntityData
from factory.mcp_utils.runtime.tool_result import ToolResult


def _empty_graph_data(tool_name: str) -> dict[str, Any]:
    if tool_name == "graph_graph_count_entities_by_run":
        return {"counts": {}, "total": 0}
    if tool_name == "graph_graph_get_findings_for_run":
        return {"rows": [], "count": 0}
    if tool_name == "graph_graph_find_entities":
        return {"entities": [], "count": 0}
    raise AssertionError(f"unexpected tool: {tool_name}")


def _graph_data(tool_name: str, raw: dict[str, Any]) -> Any:
    if tool_name == "graph_graph_find_entities":
        return SimpleNamespace(
            entities=[EntityData(**entity) for entity in raw["entities"]],
            count=raw["count"],
        )
    return SimpleNamespace(**raw)


class _Invoker:
    """Recording invoker with per-tool canned envelopes."""

    def __init__(self, envelopes: dict[str, Any] | None = None) -> None:
        self.calls: list[tuple[str, dict]] = []
        self._envelopes = envelopes or {}

    def __call__(self, tool_name: str, **kwargs: Any) -> Any:
        self.calls.append((tool_name, kwargs))
        raw = self._envelopes.get(tool_name)
        if raw is None:
            raw = _empty_graph_data(tool_name)
        return ToolResult(data=_graph_data(tool_name, raw))

    def tool_names(self) -> list[str]:
        return [c[0] for c in self.calls]


# ---------------------------------------------------------------------------
# build_findings_detail
# ---------------------------------------------------------------------------


class TestBuildFindingsDetailDelegation:
    def test_invokes_typed_findings_and_entity_lookups(self) -> None:
        inv = _Invoker(envelopes={
            "graph_graph_get_findings_for_run": {
                "rows": [{"id": "f-1", "run_id": "r1", "verdict": "CONFIRMED",
                          "file": "/a/b.py", "function": "fn"}],
                "count": 1,
            },
            "graph_graph_find_entities": {
                "entities": [{"id": "pe-1", "type": "ProvenExploit",
                              "properties": {"id": "pe-1", "run_id": "r1",
                                             "method": "GET", "path": "/x"}}],
                "count": 1,
            },
        })
        out = build_findings_detail(inv, run_id="r1")

        tool_names = inv.tool_names()
        assert "graph_graph_get_findings_for_run" in tool_names
        assert tool_names.count("graph_graph_find_entities") == 2  # PE + Suspected
        assert "graph_graph_query" not in tool_names

        find_calls = [c for c in inv.calls if c[0] == "graph_graph_find_entities"]
        types = {c[1]["entity_type"] for c in find_calls}
        assert types == {"ProvenExploit", "SuspectedVuln"}
        for _, kw in find_calls:
            assert kw["properties"] == {"run_id": "r1"}

        assert len(out["findings"]) == 1
        assert out["findings"][0]["id"] == "f-1"

    def test_no_cypher_in_findings_source(self) -> None:
        path = pathlib.Path(
            "components/games/src/factory/games/runtime/"
            "workflow_report_findings.py"
        )
        text = path.read_text(encoding="utf-8")
        assert "graph_graph_query" not in text
        assert "MATCH (" not in text
        assert "graph_graph_get_findings_for_run" in text
        assert "graph_graph_find_entities" in text


# ---------------------------------------------------------------------------
# graph_counts
# ---------------------------------------------------------------------------


class TestGraphCountsDelegation:
    def test_invokes_count_and_findings_typed_tools(self) -> None:
        inv = _Invoker(envelopes={
            "graph_graph_count_entities_by_run": {
                "counts": {"SuspectedVuln": 5, "Finding": 3,
                           "ProvenExploit": 1, "EndpointInventory": 1},
                "total": 10,
            },
            "graph_graph_get_findings_for_run": {
                "rows": [{"verdict": "CONFIRMED"}, {"verdict": "CONFIRMED"},
                         {"verdict": "REJECTED"}],
                "count": 3,
            },
            "graph_graph_find_entities": {
                "entities": [{"id": "ep-1", "type": "EndpointInventory",
                              "properties": {"count": 42}}],
                "count": 1,
            },
        })
        out = graph_counts(inv, run_id="r1")

        tool_names = inv.tool_names()
        assert "graph_graph_count_entities_by_run" in tool_names
        assert "graph_graph_get_findings_for_run" in tool_names
        assert "graph_graph_find_entities" in tool_names
        assert "graph_graph_query" not in tool_names

        count_call = next(
            c for c in inv.calls if c[0] == "graph_graph_count_entities_by_run"
        )
        assert count_call[1]["run_id"] == "r1"
        assert set(count_call[1]["labels"]) >= {
            "SuspectedVuln", "Finding", "ProvenExploit", "EndpointInventory"
        }

        assert out["suspected_vuln_count"] == 5
        assert out["finding_count"] == 3
        assert out["proven_exploit_count"] == 1
        assert out["endpoints_discovered"] == 42
        assert out["finding_verdicts"] == {"CONFIRMED": 2, "REJECTED": 1}

    def test_no_cypher_in_graph_source(self) -> None:
        path = pathlib.Path(
            "components/games/src/factory/games/runtime/workflow_report_graph.py"
        )
        text = path.read_text(encoding="utf-8")
        assert "graph_graph_query" not in text
        assert "MATCH (" not in text
        assert "RETURN count(" not in text
        assert "graph_graph_count_entities_by_run" in text


# ---------------------------------------------------------------------------
# Property tests
# ---------------------------------------------------------------------------


class TestWorkflowReportProperties:
    @given(
        run_id=st.text(min_size=1, max_size=15,
                       alphabet=st.characters(whitelist_categories=("L", "N"))),
        n_findings=st.integers(min_value=0, max_value=5),
        n_exploits=st.integers(min_value=0, max_value=5),
    )
    @settings(max_examples=30, deadline=None)
    def test_findings_detail_passes_run_id(
        self, run_id: str, n_findings: int, n_exploits: int,
    ) -> None:
        rows = [{"id": f"f-{i}", "run_id": run_id, "verdict": "CONFIRMED"}
                for i in range(n_findings)]
        exploits = [{"id": f"e-{i}", "type": "ProvenExploit",
                     "properties": {"id": f"e-{i}", "run_id": run_id}}
                    for i in range(n_exploits)]
        inv = _Invoker(envelopes={
            "graph_graph_get_findings_for_run": {"rows": rows, "count": len(rows)},
            "graph_graph_find_entities": {"entities": exploits,
                                          "count": len(exploits)},
        })
        build_findings_detail(inv, run_id=run_id)
        for tool_name, kwargs in inv.calls:
            if tool_name == "graph_graph_get_findings_for_run":
                assert kwargs["run_id"] == run_id
            elif tool_name == "graph_graph_find_entities":
                assert kwargs["properties"]["run_id"] == run_id

    @given(
        verdicts=st.lists(
            st.sampled_from(["CONFIRMED", "REJECTED", "NEEDS_REVIEW",
                             "unknown"]),
            min_size=0, max_size=20,
        ),
    )
    @settings(max_examples=30, deadline=None)
    def test_graph_counts_verdict_histogram_sums_correctly(
        self, verdicts: list[str],
    ) -> None:
        rows = [{"verdict": v} for v in verdicts]
        inv = _Invoker(envelopes={
            "graph_graph_count_entities_by_run": {
                "counts": {"Finding": len(rows)}, "total": len(rows),
            },
            "graph_graph_get_findings_for_run": {
                "rows": rows, "count": len(rows),
            },
        })
        out = graph_counts(inv, run_id="r1")
        assert sum(out["finding_verdicts"].values()) == len(rows)
