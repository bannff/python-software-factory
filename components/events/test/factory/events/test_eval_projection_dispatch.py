"""Post-commit projection tests for immutable Evals records."""
from __future__ import annotations

from typing import Any

from factory.events.runtime._dispatch_evals import _persist_eval_result
from factory.mcp_utils.interface import ToolResult

_POINTER = {
    "collection": "eval_results", "doc_id": "eval-run-1",
    "record_kind": "evaluation_run", "schema_version": 1,
    "revision": "v1", "content_hash": "sha256:stable",
}


def _durable(status: str = "created") -> dict[str, Any]:
    data = {
        "persisted": status in {"created", "matched"}, "status": status,
        "pointer": _POINTER, "projection_key": "eval-record:sha256:stable",
    }
    return {"schema_version": "v1", "ok": True, "data": data, "error": None,
            "idempotency_key": None}


def _inputs() -> tuple[dict[str, Any], dict[str, Any]]:
    return (
        {"run_id": "run-1", "workflow_id": "workflow-1"},
        {
            "summary": {"avg_score": 0.75, "pass_rate": 0.8},
            "results": [{"evaluator": "judge", "score": 0.75, "case": {"secret": 1}}],
        },
    )


def test_commit_precedes_pointer_only_projections() -> None:
    calls: list[tuple[str, dict[str, Any]]] = []

    def invoker(name: str, **kwargs: Any) -> dict[str, Any]:
        calls.append((name, kwargs))
        return _durable() if name == "evals_record_run" else {}

    _persist_eval_result(invoker, *_inputs())

    assert [name for name, _ in calls] == ["evals_record_run", "blockchain_reward_release", "events_publish", "graph_add_entity"]
    event = calls[2][1]["payload"]
    graph = calls[3][1]
    assert graph["entity_id"] == "eval-record-eval-run-1"
    assert graph["entity_type"] == "EvalRecordPointer"
    assert graph["properties"] == event
    assert set(event) == {"pointer", "projection_key", "run_id", "workflow_id", "summary"}
    assert event["pointer"] == _POINTER
    assert event["summary"] == {"avg_score": 0.75, "pass_rate": 0.8}


def test_durable_failure_prevents_all_projections() -> None:
    calls: list[str] = []

    def invoker(name: str, **kwargs: Any) -> dict[str, Any]:
        calls.append(name)
        return {"persisted": False, "status": "conflict"}

    _persist_eval_result(invoker, *_inputs())

    assert calls == ["evals_record_run"]


def test_event_failure_does_not_suppress_graph_pointer() -> None:
    calls: list[str] = []

    def invoker(name: str, **kwargs: Any) -> dict[str, Any]:
        calls.append(name)
        if name == "evals_record_run":
            return _durable()
        if name == "events_publish":
            raise RuntimeError("event bus unavailable")
        return {}

    _persist_eval_result(invoker, *_inputs())

    assert calls == ["evals_record_run", "blockchain_reward_release", "events_publish", "graph_add_entity"]


def test_graph_failure_does_not_suppress_lifecycle_event() -> None:
    calls: list[str] = []

    def invoker(name: str, **kwargs: Any) -> dict[str, Any]:
        calls.append(name)
        if name == "evals_record_run":
            return _durable()
        if name == "graph_add_entity":
            raise RuntimeError("graph unavailable")
        return {}

    _persist_eval_result(invoker, *_inputs())

    assert calls == ["evals_record_run", "blockchain_reward_release", "events_publish", "graph_add_entity"]


def test_created_and_matched_replays_keep_projection_identity() -> None:
    calls: list[tuple[str, dict[str, Any]]] = []
    statuses = iter(("created", "matched"))

    def invoker(name: str, **kwargs: Any) -> dict[str, Any]:
        calls.append((name, kwargs))
        return _durable(next(statuses)) if name == "evals_record_run" else {}

    _persist_eval_result(invoker, *_inputs())
    _persist_eval_result(invoker, *_inputs())

    events = [kwargs["payload"] for name, kwargs in calls if name == "events_publish"]
    graphs = [kwargs for name, kwargs in calls if name == "graph_add_entity"]
    assert events[0] == events[1]
    assert graphs[0]["entity_id"] == graphs[1]["entity_id"]
    assert graphs[0]["properties"] == graphs[1]["properties"]


def test_direct_tool_result_commit_keeps_pointer_projections() -> None:
    calls: list[str] = []

    def invoker(name: str, **kwargs: Any) -> Any:
        calls.append(name)
        if name == "evals_record_run":
            return ToolResult(ok=True, data=_durable()["data"])
        return {}

    _persist_eval_result(invoker, *_inputs())

    assert calls == ["evals_record_run", "blockchain_reward_release", "events_publish", "graph_add_entity"]


def test_failed_direct_tool_result_prevents_projections() -> None:
    calls: list[str] = []

    def invoker(name: str, **kwargs: Any) -> Any:
        calls.append(name)
        return ToolResult(ok=False, data=None, error="durable write failed")

    _persist_eval_result(invoker, *_inputs())

    assert calls == ["evals_record_run"]
