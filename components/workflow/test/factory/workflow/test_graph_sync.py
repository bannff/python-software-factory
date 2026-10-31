"""Workflow graph projection correlation authority regressions."""
from __future__ import annotations

from typing import Any

import factory.workflow.runtime.graph_sync as graph_sync


def _capture(monkeypatch) -> list[tuple[str, dict[str, Any]]]:
    calls: list[tuple[str, dict[str, Any]]] = []
    monkeypatch.setattr(
        graph_sync, "_invoke",
        lambda tool_name, **kwargs: calls.append((tool_name, kwargs)),
    )
    return calls


def test_run_projection_uses_durable_run_over_caller_run(monkeypatch) -> None:
    calls = _capture(monkeypatch)

    graph_sync.sync_run(
        {"run_id": "wfr:v1:durable", "workflow_id": "workflow"},
        {"workflow_run_id": "caller-run", "session_id": "session"},
    )

    properties = calls[0][1]["properties"]
    assert properties["run_id"] == "wfr:v1:durable"
    assert properties["correlation_id"] == "wfr:v1:durable"
    assert properties["session_id"] == "session"
    assert "workflow_run_id" not in properties


def test_activity_projection_uses_payload_run_over_caller_run(monkeypatch) -> None:
    calls = _capture(monkeypatch)

    graph_sync.sync_activity(
        "workflow.run_started",
        {"run_id": "wfr:v1:durable", "status": "running"},
        {"run_id": "caller-run", "trace_id": "trace"},
    )

    properties = calls[0][1]["properties"]
    assert properties["run_id"] == "wfr:v1:durable"
    assert properties["trace_id"] == "trace"
    assert "workflow_run_id" not in properties
