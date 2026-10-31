"""Typed storage result compatibility for workflow improvement."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from factory.events.runtime.learning_contracts import (
    VERDICT_BASELINE_SET,
    VERDICT_IMPROVED,
)
from factory.events.runtime.learning_handlers.improvement import (
    handle_workflow_improvement,
)
from factory.events.runtime.models import Event
from factory.mcp_utils.interface import ToolResult
from factory.storage.mcp.contracts.operational import DocumentData, DocFindOutput

_T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _doc(run_id: str, f1: float, when: datetime) -> dict[str, Any]:
    return {"id": f"eval-{run_id}", "data": {
        "run_id": run_id, "workflow_type": "dast",
        "target_app": "WebGoat", "vuln_class": "IDOR",
        "f1": f1, "created_at": when.isoformat(),
    }}


def _priors(scores: list[float]) -> list[dict[str, Any]]:
    return [
        _doc(f"run-{i}", score, _T0 - timedelta(days=i + 1))
        for i, score in enumerate(scores)
    ]


def _event(score: float = 0.5) -> Event:
    return Event(
        source="events.rewards", type="reward.computed",
        payload={
            "run_id": "run-current", "workflow_run_id": "wf-current",
            "workflow_type": "dast", "target_app": "WebGoat",
            "vuln_class": "IDOR", "score": score, "profile_version": "v1",
        },
    )


def test_storage_doc_find_tool_result_models_preserve_baseline_behavior() -> None:
    documents = [
        DocumentData(id=row["id"], data=row["data"])
        for row in _priors([0.4, 0.5, 0.6])
    ]

    def successful(tool_name: str, **kwargs: Any) -> Any:
        if tool_name == "events_query_events":
            return {"events": [], "total": 0}
        if tool_name == "storage_doc_find":
            return ToolResult(data=DocFindOutput(documents=documents))
        if tool_name == "events_publish":
            return {"event_id": "evt-improvement"}
        raise AssertionError(tool_name)

    result = handle_workflow_improvement(_event(score=0.8), successful)
    assert result["verdict"] == VERDICT_IMPROVED

    def failed(tool_name: str, **kwargs: Any) -> Any:
        if tool_name == "events_query_events":
            return {"events": [], "total": 0}
        if tool_name == "storage_doc_find":
            return ToolResult(ok=False, error="storage unavailable")
        if tool_name == "events_publish":
            return {"event_id": "evt-improvement"}
        raise AssertionError(tool_name)

    assert handle_workflow_improvement(_event(), failed)["verdict"] == VERDICT_BASELINE_SET
