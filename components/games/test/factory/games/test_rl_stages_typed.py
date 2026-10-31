"""Pin ``_collect_findings`` to typed graph tools (no Cypher).

Tracked under bd python-factory-ky0i / epic python-factory-kzd8. The
previous Cypher escape hatch silently produced empty results on
networkx (local dev). These tests assert that the migration is
behavioural — typed tool names get invoked, no ``graph_graph_query``
remains in the source, and run_id propagates through every row.
"""
from __future__ import annotations

import pathlib
from typing import Any

from hypothesis import given, settings, strategies as st

from factory.games.runtime._rl_stages import _collect_findings
from factory.graph.mcp.core_models import EntityData, EntitySearchData
from factory.mcp_utils.runtime.tool_result import ToolResult


class _RecordingInvoker:
    """Minimal callable invoker that records calls + returns canned envelopes."""

    def __init__(self, finding_rows: list[dict] | None = None,
                 exploit_props: list[dict] | None = None,
                 raise_on: str | None = None) -> None:
        self.calls: list[tuple[str, dict]] = []
        self._findings = finding_rows or []
        self._exploits = exploit_props or []
        self._raise_on = raise_on

    def __call__(self, tool_name: str, **kwargs: Any) -> Any:
        self.calls.append((tool_name, kwargs))
        if tool_name == self._raise_on:
            raise RuntimeError(f"forced failure for {tool_name}")
        if tool_name == "graph_graph_get_findings_for_run":
            return ToolResult(data=type("FindingsData", (), {
                "rows": list(self._findings),
                "count": len(self._findings),
                "run_id": kwargs.get("run_id"),
            })())
        if tool_name == "graph_graph_find_entities":
            entities = [
                EntityData(id=f"pe-{i}", type="ProvenExploit", properties=props)
                for i, props in enumerate(self._exploits)
            ]
            return ToolResult(data=EntitySearchData(entities=entities, count=len(entities)))
        raise AssertionError(f"unexpected tool: {tool_name}")


class TestCollectFindingsTypedDelegation:
    """``_collect_findings`` must call the typed tools, never Cypher."""

    def test_invokes_typed_findings_and_proven_exploits(self) -> None:
        inv = _RecordingInvoker(
            finding_rows=[{"id": "f-1", "run_id": "r1", "verdict": "CONFIRMED"}],
            exploit_props=[{"id": "pe-1", "run_id": "r1", "method": "GET"}],
        )
        rows = _collect_findings(inv, run_id="r1")

        tool_names = [c[0] for c in inv.calls]
        assert "graph_graph_get_findings_for_run" in tool_names
        assert "graph_graph_find_entities" in tool_names
        assert "graph_graph_query" not in tool_names

        # First call is the typed findings tool, scoped to run_id.
        first_call = inv.calls[0]
        assert first_call[0] == "graph_graph_get_findings_for_run"
        assert first_call[1]["run_id"] == "r1"

        # Second call is find_entities for ProvenExploit, run-scoped.
        second_call = inv.calls[1]
        assert second_call[0] == "graph_graph_find_entities"
        assert second_call[1]["entity_type"] == "ProvenExploit"
        assert second_call[1]["properties"] == {"run_id": "r1"}

        ids = {row.get("id") for row in rows}
        assert ids == {"f-1", "pe-1"}

    def test_findings_failure_still_returns_proven_exploits(self) -> None:
        """Typed findings call failure must not block proven-exploit collection."""
        inv = _RecordingInvoker(
            exploit_props=[{"id": "pe-1", "run_id": "r1"}],
            raise_on="graph_graph_get_findings_for_run",
        )
        rows = _collect_findings(inv, run_id="r1")
        assert any(r.get("id") == "pe-1" for r in rows)

    def test_exploit_failure_still_returns_findings(self) -> None:
        """ProvenExploit failure must not block typed findings."""
        inv = _RecordingInvoker(
            finding_rows=[{"id": "f-1", "run_id": "r1"}],
            raise_on="graph_graph_find_entities",
        )
        rows = _collect_findings(inv, run_id="r1")
        assert any(r.get("id") == "f-1" for r in rows)

    def test_returns_empty_list_on_total_failure(self) -> None:
        def boom(_tool: str, **_kw: Any) -> Any:
            raise RuntimeError("graph offline")

        rows = _collect_findings(boom, run_id="r1")
        assert rows == []

    def test_no_cypher_in_source(self) -> None:
        """Source must contain no Cypher fragments or graph_graph_query usage."""
        path = pathlib.Path(
            "components/games/src/factory/games/runtime/_rl_stages.py"
        )
        text = path.read_text(encoding="utf-8")
        assert "graph_graph_query" not in text
        assert "MATCH (" not in text
        assert "graph_graph_get_findings_for_run" in text
        assert "graph_graph_find_entities" in text


class TestCollectFindingsProperties:
    """Hypothesis property: run_id flows through to row run_id when present."""

    @given(
        run_id=st.text(min_size=1, max_size=20,
                       alphabet=st.characters(whitelist_categories=("L", "N"))),
        n_findings=st.integers(min_value=0, max_value=8),
        n_exploits=st.integers(min_value=0, max_value=8),
    )
    @settings(max_examples=40, deadline=None)
    def test_collected_rows_carry_run_id(
        self, run_id: str, n_findings: int, n_exploits: int,
    ) -> None:
        finding_rows = [{"id": f"f-{i}", "run_id": run_id} for i in range(n_findings)]
        exploit_props = [{"id": f"pe-{i}", "run_id": run_id} for i in range(n_exploits)]
        inv = _RecordingInvoker(
            finding_rows=finding_rows, exploit_props=exploit_props,
        )
        rows = _collect_findings(inv, run_id=run_id)

        assert len(rows) == n_findings + n_exploits
        for row in rows:
            assert row.get("run_id") == run_id

    @given(
        run_id=st.text(min_size=1, max_size=15,
                       alphabet=st.characters(whitelist_categories=("L", "N"))),
    )
    @settings(max_examples=20, deadline=None)
    def test_run_id_propagates_to_typed_calls(self, run_id: str) -> None:
        inv = _RecordingInvoker()
        _collect_findings(inv, run_id=run_id)
        for tool_name, kwargs in inv.calls:
            if tool_name == "graph_graph_get_findings_for_run":
                assert kwargs["run_id"] == run_id
            elif tool_name == "graph_graph_find_entities":
                assert kwargs["properties"]["run_id"] == run_id


def test_failed_tool_results_are_skipped_without_losing_other_labels() -> None:
    class _FailedFindingsInvoker(_RecordingInvoker):
        def __call__(self, tool_name: str, **kwargs: Any) -> Any:
            if tool_name == "graph_graph_get_findings_for_run":
                return ToolResult(ok=False, data=None, error="graph unavailable")
            return super().__call__(tool_name, **kwargs)

    rows = _collect_findings(
        _FailedFindingsInvoker(exploit_props=[{"id": "pe-1", "run_id": "r1"}]),
        run_id="r1",
    )
    assert rows == [{"id": "pe-1", "run_id": "r1"}]