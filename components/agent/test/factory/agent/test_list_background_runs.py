"""agent.list_background_runs — row 80 rail badge, zero-new-runtime read path."""
from __future__ import annotations

import asyncio

import pytest
from factory.mcp_utils.interface import get_service, set_service

from factory.agent.runtime.background.list_runs import (
    BackgroundListError, list_background_runs,
)

RUN_SUBAGENT = {
    "run_id": "run-1", "status": "running", "started_at": "2026-09-15T00:00:00Z",
    "input": {"launch_metadata": {
        "kind": "background_subagent", "origin_thread_id": "thread-1", "persona_id": "worker",
    }},
}
RUN_LOOP_CYCLE = {
    "run_id": "run-2", "status": "succeeded", "started_at": "2026-09-15T00:01:00Z",
    "input": {"launch_metadata": {
        "kind": "workflow_loop_cycle", "origin_thread_id": "thread-2", "persona_id": "loop-agent",
    }},
}
RUN_UNRELATED = {
    "run_id": "run-3", "status": "running", "started_at": "2026-09-15T00:02:00Z",
    "input": {},
}


def _invoker_returning(runs: list[dict]):
    def factory(caller: str):
        def invoke(target, *, arguments, idempotency_key, envelope):
            assert target == {"brick_name": "workflow", "tool_name": "workflow.list_runs"}
            return {"ok": True, "result": {"structured_content": {
                "ok": True, "data": {"runs": runs},
            }}}
        return invoke
    return factory


@pytest.fixture(autouse=True)
def _restore_invoker():
    previous = get_service("tool_invoker_for_caller")
    yield
    set_service("tool_invoker_for_caller", previous)


def test_filters_to_background_kinds_only():
    set_service("tool_invoker_for_caller", _invoker_returning([RUN_SUBAGENT, RUN_LOOP_CYCLE, RUN_UNRELATED]))
    rows = asyncio.run(list_background_runs({}, None, False, 50))
    assert [r["run_id"] for r in rows] == ["run-1", "run-2"]
    assert rows[0]["kind"] == "background_subagent" and rows[0]["persona_id"] == "worker"


def test_filters_by_origin_thread_id():
    set_service("tool_invoker_for_caller", _invoker_returning([RUN_SUBAGENT, RUN_LOOP_CYCLE]))
    rows = asyncio.run(list_background_runs({}, "thread-2", False, 50))
    assert [r["run_id"] for r in rows] == ["run-2"]


def test_active_only_excludes_terminal_statuses():
    set_service("tool_invoker_for_caller", _invoker_returning([RUN_SUBAGENT, RUN_LOOP_CYCLE]))
    rows = asyncio.run(list_background_runs({}, None, True, 50))
    assert [r["run_id"] for r in rows] == ["run-1"]


def test_limit_is_honored():
    set_service("tool_invoker_for_caller", _invoker_returning([RUN_SUBAGENT, RUN_LOOP_CYCLE]))
    rows = asyncio.run(list_background_runs({}, None, False, 1))
    assert len(rows) == 1


def test_missing_invoker_raises_typed_error():
    set_service("tool_invoker_for_caller", None)
    with pytest.raises(BackgroundListError, match="background_runtime_unavailable"):
        asyncio.run(list_background_runs({}, None, False, 50))


def test_workflow_failure_raises_typed_error():
    def factory(caller: str):
        return lambda *a, **k: {"ok": False}
    set_service("tool_invoker_for_caller", factory)
    with pytest.raises(BackgroundListError, match="workflow_transport_failed"):
        asyncio.run(list_background_runs({}, None, False, 50))
