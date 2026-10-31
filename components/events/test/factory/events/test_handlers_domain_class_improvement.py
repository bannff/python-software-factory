"""Domain-class workflow-improvement and typed Graph dispatch tests."""
from __future__ import annotations

from typing import Any

from factory.events.runtime.dispatch_args import _build_metrics_payload, _count_findings
from factory.events.runtime.learning_handlers import handle_workflow_improvement
from factory.events.runtime.models import Event
from factory.graph.mcp.evidence_models import CountsData, RowsData
from factory.mcp_utils.runtime.tool_result import ToolResult
from factory.storage.mcp.contracts.operational import DocumentData, DocFindOutput


def _count_result(
    *, run_id: str, labels: list[str], counts: dict[str, int],
) -> ToolResult[CountsData]:
    return ToolResult(data=CountsData(
        run_id=run_id, labels=labels, counts=counts, total=sum(counts.values()),
    ))


def _rows_result(rows: list[dict[str, object]]) -> ToolResult[RowsData]:
    return ToolResult(data=RowsData(rows=rows, count=len(rows)))


class _Recorder:
    def __init__(self, returns: dict[str, Any] | None = None) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self._returns = returns or {}

    def __call__(self, tool: str, **kwargs: Any) -> Any:
        self.calls.append((tool, kwargs))
        if tool in self._returns:
            value = self._returns[tool]
            return value(**kwargs) if callable(value) else value
        return {}


def test_improvement_handler_buckets_query_by_domain_class() -> None:
    captured_query: dict[str, Any] = {}

    def storage_returns(**kwargs: Any) -> dict[str, object]:
        captured_query.update(kwargs)
        return {"documents": []}

    invoker = _Recorder({
        "events_query_events": {"events": [], "total": 0},
        "storage_doc_find": storage_returns,
        "events_publish": {"event_id": "evt-imp"},
    })
    event = Event(
        source="events.rewards", type="reward.computed",
        payload={
            "run_id": "run-1", "workflow_run_id": "wf-1",
            "domain_class": "wine", "vuln_class": "TASTING",
            "workflow_type": "dast", "target_app": "WineApp", "score": 0.5,
        },
    )
    handle_workflow_improvement(event, invoker)
    assert captured_query["query"]["domain_class"] == "wine"
    assert "vuln_class" not in captured_query["query"]


def test_improvement_handler_security_default_buckets_by_vuln_class() -> None:
    captured_query: dict[str, Any] = {}

    def storage_returns(**kwargs: Any) -> dict[str, object]:
        captured_query.update(kwargs)
        return {"documents": []}

    invoker = _Recorder({
        "events_query_events": {"events": [], "total": 0},
        "storage_doc_find": storage_returns,
        "events_publish": {"event_id": "evt-imp"},
    })
    event = Event(
        source="events.rewards", type="reward.computed",
        payload={
            "run_id": "run-1", "workflow_run_id": "wf-1", "vuln_class": "IDOR",
            "workflow_type": "dast", "target_app": "WebGoat", "score": 0.5,
        },
    )
    handle_workflow_improvement(event, invoker)
    assert captured_query["query"]["vuln_class"] == "IDOR"
    assert "domain_class" not in captured_query["query"]


def test_count_findings_default_labels_back_compat() -> None:
    captured: dict[str, Any] = {}

    def graph_count(**kwargs: Any) -> ToolResult[CountsData]:
        captured.update(kwargs)
        return _count_result(
            run_id=kwargs["run_id"], labels=kwargs["labels"],
            counts={"Finding": 3, "ProvenExploit": 1},
        )

    assert _count_findings(_Recorder({"graph_count_entities_by_run": graph_count}), "run-1") == 4
    assert captured["labels"] == ["Finding", "ProvenExploit"]


def test_count_findings_accepts_custom_label_list() -> None:
    captured: dict[str, Any] = {}

    def graph_count(**kwargs: Any) -> ToolResult[CountsData]:
        captured.update(kwargs)
        return _count_result(
            run_id=kwargs["run_id"], labels=kwargs["labels"], counts={"WineFinding": 2},
        )

    assert _count_findings(
        _Recorder({"graph_count_entities_by_run": graph_count}), "run-1",
        count_labels=["WineFinding"],
    ) == 2
    assert captured["labels"] == ["WineFinding"]


def test_build_metrics_payload_threads_count_labels_from_payload() -> None:
    captured: dict[str, Any] = {}

    def graph_count(**kwargs: Any) -> ToolResult[CountsData]:
        captured.update(kwargs)
        return _count_result(
            run_id=kwargs["run_id"], labels=kwargs["labels"], counts={"WineFinding": 7},
        )

    invoker = _Recorder({
        "graph_count_entities_by_run": graph_count,
        "graph_get_tool_invocations_for_run": lambda **_kw: _rows_result([]),
    })
    event = Event(
        source="events.rewards", type="graph.completed",
        payload={"run_id": "run-1", "count_labels": ["WineFinding"]},
    )
    payload = _build_metrics_payload(event, invoker)
    assert captured["labels"] == ["WineFinding"]
    assert payload["payload"]["findings_count"] == 7


def test_improvement_handler_accepts_real_storage_doc_find_tool_result() -> None:
    documents = [
        DocumentData(id=f"prior-{index}", data={
            "run_id": f"prior-{index}", "f1": score,
            "created_at": f"2026-07-0{index}T00:00:00Z",
        })
        for index, score in enumerate((0.4, 0.5, 0.6), start=1)
    ]
    invoker = _Recorder({
        "events_query_events": {"events": [], "total": 0},
        "storage_doc_find": ToolResult(data=DocFindOutput(documents=documents)),
        "events_publish": {"event_id": "evt-imp"},
    })
    event = Event(
        source="events.rewards", type="reward.computed",
        payload={
            "run_id": "current", "workflow_run_id": "wf-1", "vuln_class": "IDOR",
            "workflow_type": "dast", "target_app": "WebGoat", "score": 0.8,
        },
    )

    result = handle_workflow_improvement(event, invoker)

    assert result["verdict"] == "improved"
    assert result["baseline_score"] == 0.5


def test_improvement_handler_treats_failed_storage_tool_result_as_empty_history() -> None:
    invoker = _Recorder({
        "events_query_events": {"events": [], "total": 0},
        "storage_doc_find": ToolResult(ok=False, error="storage unavailable"),
        "events_publish": {"event_id": "evt-imp"},
    })
    event = Event(
        source="events.rewards", type="reward.computed",
        payload={
            "run_id": "current", "workflow_run_id": "wf-1", "vuln_class": "IDOR",
            "workflow_type": "dast", "target_app": "WebGoat", "score": 0.8,
        },
    )

    result = handle_workflow_improvement(event, invoker)

    assert result["verdict"] == "baseline_set"
    assert result["baseline_run_ids"] == []
