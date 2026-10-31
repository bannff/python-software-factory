"""Tests for graph-backed Evals persistence through typed Graph MCP responses."""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from factory.evals.runtime.adapters.graph_adapter import GraphEvalsStore
from factory.evals.runtime.ports import EvalCase, EvalMetrics, EvalRun, EvalSuite
from factory.mcp_utils.interface import ToolResult


def _make_run(id_="r1", suite_id="s1", status="completed") -> EvalRun:
    now = datetime.now(timezone.utc)
    return EvalRun(
        id=id_, suite_id=suite_id, started_at=now, completed_at=now, status=status,
    )


def _make_metrics(pass_rate=0.9, total=10, passed=9, failed=1) -> EvalMetrics:
    return EvalMetrics(
        total_cases=total, passed=passed, failed=failed, pass_rate=pass_rate,
    )


def _make_suite(id_="s1", name="smoke", desc="desc", n_cases=3) -> EvalSuite:
    cases = [
        EvalCase(id=f"c{i}", name=f"case-{i}", input={"q": "hi"})
        for i in range(n_cases)
    ]
    return EvalSuite(id=id_, name=name, description=desc, cases=cases)


def _run_result(*properties: dict[str, object]) -> ToolResult:
    entities = [SimpleNamespace(properties=row) for row in properties]
    return ToolResult(data=SimpleNamespace(entities=entities))


class TestGraphEvalsStore:
    def test_persist_run_creates_node_and_relationship(self):
        invoker = MagicMock(return_value={})
        GraphEvalsStore(invoker).persist_run(_make_run(), _make_metrics())

        calls = invoker.call_args_list
        assert len(calls) == 2
        assert calls[0].args[0] == "graph_graph_add_entity"
        assert calls[0].kwargs["entity_type"] == "EvalRun"
        assert calls[0].kwargs["properties"]["suite_id"] == "s1"
        assert calls[0].kwargs["properties"]["pass_rate"] == 0.9
        assert calls[1].args[0] == "graph_graph_add_relationship"
        assert calls[1].kwargs["relationship_type"] == "EVALUATED_BY"

    def test_persist_suite_creates_node(self):
        invoker = MagicMock(return_value={})
        GraphEvalsStore(invoker).persist_suite(_make_suite())

        call = invoker.call_args
        assert call.args[0] == "graph_graph_add_entity"
        assert call.kwargs["entity_type"] == "EvalSuite"
        assert call.kwargs["properties"]["name"] == "smoke"
        assert call.kwargs["properties"]["description"] == "desc"
        assert call.kwargs["properties"]["case_count"] == 3

    def test_query_runs_projects_typed_entities_and_sorts_descending(self):
        invoker = MagicMock(return_value=_run_result(
            {"suite_id": "s1", "run_at": "2026-01-01T00:00:00+00:00"},
            {"suite_id": "s2", "run_at": "2026-02-01T00:00:00+00:00"},
        ))
        result = GraphEvalsStore(invoker).query_runs()
        assert result == [
            {"suite_id": "s2", "run_at": "2026-02-01T00:00:00+00:00"},
            {"suite_id": "s1", "run_at": "2026-01-01T00:00:00+00:00"},
        ]
        invoker.assert_called_once_with(
            "graph_graph_find_entities", entity_type="EvalRun", limit=100,
        )

    def test_query_runs_filters_typed_entity_properties_locally(self):
        invoker = MagicMock(return_value=_run_result(
            {"suite_id": "s1", "run_at": "2026-01-01"},
            {"suite_id": "s2", "run_at": "2026-02-01"},
        ))
        assert GraphEvalsStore(invoker).query_runs(suite_id="s1") == [
            {"suite_id": "s1", "run_at": "2026-01-01"},
        ]

    @pytest.mark.parametrize("result", [
        ToolResult(ok=False, data=None, error="graph offline"), None,
    ])
    def test_query_runs_returns_empty_for_failed_or_empty_typed_result(self, result):
        assert GraphEvalsStore(MagicMock(return_value=result)).query_runs() == []

    def test_health_check_reads_typed_graph_health(self):
        result = ToolResult(data=SimpleNamespace(
            healthy=True,
            graphs={"networkx": SimpleNamespace(nodes=42)},
        ))
        assert GraphEvalsStore(MagicMock(return_value=result)).health_check() == {
            "ok": True, "backend": "graph", "graph_nodes": 42,
        }

    @pytest.mark.parametrize("method", ["persist_run", "persist_suite"])
    def test_write_errors_propagate(self, method):
        store = GraphEvalsStore(MagicMock(side_effect=RuntimeError("boom")))
        with pytest.raises(RuntimeError, match="boom"):
            getattr(store, method)(_make_run() if method == "persist_run" else _make_suite(), *(() if method == "persist_suite" else (_make_metrics(),)))

    def test_query_errors_keep_existing_empty_shape(self):
        assert GraphEvalsStore(MagicMock(side_effect=RuntimeError("boom"))).query_runs() == []


_id_st = st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("L", "N")))
_rate_st = st.floats(min_value=0.0, max_value=1.0, allow_nan=False)
_count_st = st.integers(min_value=0, max_value=10_000)
_text_st = st.text(min_size=0, max_size=200)


@settings(max_examples=50)
@given(run_id=_id_st, suite_id=_id_st, pass_rate=_rate_st, total=_count_st)
def test_persist_run_properties(run_id, suite_id, pass_rate, total):
    invoker = MagicMock(return_value={})
    run = _make_run(id_=run_id, suite_id=suite_id)
    GraphEvalsStore(invoker).persist_run(run, _make_metrics(pass_rate=pass_rate, total=total))
    props = invoker.call_args_list[0].kwargs["properties"]
    assert props["suite_id"] == suite_id
    assert props["pass_rate"] == pass_rate
    assert props["total_cases"] == total
    assert invoker.call_args_list[0].kwargs["entity_id"] == f"eval-run-{run_id}"


@settings(max_examples=50)
@given(suite_id=_id_st, name=_text_st, desc=_text_st)
def test_persist_suite_properties(suite_id, name, desc):
    invoker = MagicMock(return_value={})
    GraphEvalsStore(invoker).persist_suite(_make_suite(id_=suite_id, name=name, desc=desc))
    call = invoker.call_args
    assert call.kwargs["properties"]["name"] == name
    assert call.kwargs["entity_id"] == f"eval-suite-{suite_id}"
