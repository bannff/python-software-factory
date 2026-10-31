"""Pin dispatch helpers to canonical typed Graph tools and their envelopes."""
from __future__ import annotations

from typing import Any, Callable

import pytest
from hypothesis import given, settings, strategies as st

from factory.events.runtime.dispatch_args import _build_metrics_payload, _fetch_trace_summary
from factory.events.runtime.models import Event
from factory.graph.mcp.evidence_models import CountsData, RowsData
from factory.mcp_utils.runtime.tool_result import ToolResult


def _count_result(
    *, run_id: str, labels: list[str], counts: dict[str, int],
) -> ToolResult[CountsData]:
    return ToolResult(data=CountsData(
        run_id=run_id, labels=labels, counts=counts, total=sum(counts.values()),
    ))


def _rows_result(rows: list[dict[str, object]]) -> ToolResult[RowsData]:
    return ToolResult(data=RowsData(rows=rows, count=len(rows)))


def _recorder(handlers: dict[str, Callable[..., Any]] | None = None):
    """Return an invoker and its calls; raw Cypher is an explicit violation."""
    handlers = handlers or {}
    calls: list[tuple[str, dict[str, Any]]] = []

    def invoker(tool_name: str, **kwargs: Any) -> Any:
        calls.append((tool_name, kwargs))
        if tool_name in handlers:
            return handlers[tool_name](**kwargs)
        if tool_name == "graph_find_entities":
            raise AssertionError("dispatch_args must use typed Graph tools only")
        raise AssertionError(f"unexpected tool: {tool_name}")

    return invoker, calls


def _metrics_event(run_id: str = "run-x") -> Event:
    return Event(
        source="agent.graph", type="graph.completed",
        payload={"run_id": run_id, "graph_id": "g1", "execution_time": 1.25},
    )


def test_fetch_trace_summary_uses_typed_tool() -> None:
    rows = [
        {"tool_name": "graph_find_entities", "success": True, "latency_ms": 12.0},
        {"tool_name": "kb_search", "success": False, "latency_ms": 31.5},
    ]
    invoker, calls = _recorder({
        "graph_get_tool_invocations_for_run": lambda **_kw: _rows_result(rows),
    })
    out = _fetch_trace_summary("run-1", invoker)
    assert calls == [("graph_get_tool_invocations_for_run", {"run_id": "run-1", "limit": 50})]
    assert "Tool trace (2 calls)" in out
    assert "graph_find_entities ok=True 12ms" in out
    assert "kb_search ok=False 32ms" in out


def test_fetch_trace_summary_no_run_id_skips_invoke() -> None:
    invoker, calls = _recorder()
    assert "No run_id" in _fetch_trace_summary("", invoker)
    assert calls == []


def test_fetch_trace_summary_handles_empty_and_exception() -> None:
    invoker, _ = _recorder({
        "graph_get_tool_invocations_for_run": lambda **_kw: _rows_result([]),
    })
    assert "No tool trace found for run run-1" in _fetch_trace_summary("run-1", invoker)

    def boom(**_kw: Any) -> ToolResult[RowsData]:
        raise RuntimeError("graph backend down")

    invoker2, _ = _recorder({"graph_get_tool_invocations_for_run": boom})
    assert "Trace fetch failed" in _fetch_trace_summary("run-1", invoker2)


def test_build_metrics_payload_uses_typed_tools_only() -> None:
    rows = [
        {"tool_name": "t1", "success": True, "latency_ms": 100},
        {"tool_name": "t2", "success": True, "latency_ms": 200},
        {"tool_name": "t3", "success": False, "latency_ms": 300},
    ]
    invoker, calls = _recorder({
        "graph_count_entities_by_run": lambda **kw: _count_result(
            run_id=kw["run_id"], labels=kw["labels"],
            counts={"Finding": 2, "ProvenExploit": 1},
        ),
        "graph_get_tool_invocations_for_run": lambda **_kw: _rows_result(rows),
    })
    out = _build_metrics_payload(_metrics_event("run-x"), invoker)
    assert [name for name, _ in calls] == [
        "graph_count_entities_by_run", "graph_get_tool_invocations_for_run",
    ]
    assert calls[0][1] == {"run_id": "run-x", "labels": ["Finding", "ProvenExploit"]}
    assert calls[1][1] == {"run_id": "run-x", "limit": 10_000}
    payload = out["payload"]
    assert out["event_type"] == "metrics.record"
    assert payload["findings_count"] == 3
    assert payload["tool_calls"] == 3
    assert payload["tool_error_rate"] == pytest.approx(0.333, abs=1e-3)
    assert payload["tool_avg_latency_ms"] == pytest.approx(200.0)
    assert payload["cycle_efficiency"] == pytest.approx(1.0)


def test_build_metrics_payload_degrades_when_count_call_fails() -> None:
    def boom(**_kw: Any) -> ToolResult[CountsData]:
        raise RuntimeError("count backend down")

    invoker, _ = _recorder({
        "graph_count_entities_by_run": boom,
        "graph_get_tool_invocations_for_run": lambda **_kw: _rows_result([]),
    })
    payload = _build_metrics_payload(_metrics_event("run-x"), invoker)["payload"]
    assert payload["findings_count"] == 0
    assert payload["tool_calls"] == 0 and payload["tool_error_rate"] == 0


def test_build_metrics_payload_degrades_when_invocations_call_fails() -> None:
    def boom(**_kw: Any) -> ToolResult[RowsData]:
        raise RuntimeError("invocations backend down")

    invoker, _ = _recorder({
        "graph_count_entities_by_run": lambda **kw: _count_result(
            run_id=kw["run_id"], labels=kw["labels"],
            counts={"Finding": 4, "ProvenExploit": 0},
        ),
        "graph_get_tool_invocations_for_run": boom,
    })
    payload = _build_metrics_payload(_metrics_event("run-x"), invoker)["payload"]
    assert payload["findings_count"] == 4
    assert payload["tool_calls"] == 0 and payload["tool_avg_latency_ms"] == 0


def test_build_metrics_payload_no_run_id_skips_typed_calls() -> None:
    invoker, calls = _recorder()
    payload = _build_metrics_payload(_metrics_event(""), invoker)["payload"]
    assert calls == []
    assert payload["findings_count"] == 0 and payload["tool_calls"] == 0


@settings(max_examples=50, deadline=None)
@given(
    finding=st.integers(min_value=0, max_value=200),
    exploit=st.integers(min_value=0, max_value=200),
    rows=st.lists(
        st.fixed_dictionaries({
            "tool_name": st.text(min_size=1, max_size=10),
            "success": st.booleans(),
            "latency_ms": st.floats(
                min_value=0, max_value=10_000, allow_nan=False, allow_infinity=False,
            ),
        }), min_size=0, max_size=25,
    ),
)
def test_metrics_payload_matches_typed_tool_data(finding: int, exploit: int, rows: list[dict[str, object]]) -> None:
    invoker, _ = _recorder({
        "graph_count_entities_by_run": lambda **kw: _count_result(
            run_id=kw["run_id"], labels=kw["labels"],
            counts={"Finding": finding, "ProvenExploit": exploit},
        ),
        "graph_get_tool_invocations_for_run": lambda **_kw: _rows_result(rows),
    })
    payload = _build_metrics_payload(_metrics_event("run-h"), invoker)["payload"]
    assert payload["findings_count"] == finding + exploit
    assert payload["tool_calls"] == len(rows)
    if rows:
        ok = sum(1 for row in rows if row["success"])
        avg_ms = sum(float(row["latency_ms"]) for row in rows) / len(rows)
        assert payload["tool_error_rate"] == round(1 - (ok / len(rows)), 3)
        assert payload["tool_avg_latency_ms"] == round(avg_ms, 1)
    else:
        assert payload["tool_error_rate"] == 0
        assert payload["tool_avg_latency_ms"] == 0
    assert payload["cycle_efficiency"] == round((finding + exploit) / max(len(rows), 1), 3)


def test_tool_result_failures_preserve_empty_metric_and_trace_fallbacks() -> None:
    invoker, _ = _recorder({
        "graph_count_entities_by_run": lambda **_kw: ToolResult(
            ok=False, data=None, error="graph unavailable",
        ),
        "graph_get_tool_invocations_for_run": lambda **_kw: ToolResult(
            ok=False, data=None, error="graph unavailable",
        ),
    })
    payload = _build_metrics_payload(_metrics_event("run-failed"), invoker)["payload"]
    assert payload["findings_count"] == 0
    assert payload["tool_calls"] == 0
    assert payload["tool_error_rate"] == 0
    assert "No tool trace found for run run-failed" in _fetch_trace_summary("run-failed", invoker)
