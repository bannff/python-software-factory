"""Canonical managed Workflow live-event ordering after durable mutations."""
from __future__ import annotations

import threading
from pathlib import Path

from factory.workflow.runtime.envelope import Envelope

from .test_managed_graph import DIGEST, GraphInvoker, runtime, start
from .test_managed_graph_events import BlockingInvoker

_ALLOWED = {
    "workflow.run_started", "workflow.attempt_started",
    "workflow.attempt_stream_event", "workflow.attempt_completed",
    "workflow.step_transition", "workflow.run_succeeded",
    "workflow.run_failed", "workflow.run_cancelled",
}


class StreamingInvoker(GraphInvoker):
    owner = None

    def invoke(self, **kwargs):
        if kwargs["target"].tool_name == "execute_strands_graph_attempt":
            binding = kwargs["attempt"]
            self.owner.append_execution_event(
                **binding, sequence=0, terminal=False,
                raw_evidence={
                    "type": "multiagent_node_stream",
                    "event": {"type": "message", "node_id": "nested-node"},
                    "attempt": binding["attempt_id"],
                }, safe_metadata={"native_event_type": "multiagent_node_stream", "node_id": "nested-node"},
            )
        return super().invoke(**kwargs)


def _capture(monkeypatch, holder, seen):
    def publish(_tool, **kwargs):
        event_type, payload = kwargs["event_type"], kwargs["payload"]
        assert event_type in _ALLOWED
        owner = holder["owner"]
        run_id = payload["run_id"]
        run = owner.storage.get_run(run_id=run_id)
        assert run is not None
        if event_type == "workflow.run_started":
            assert run.status in {"pending", "running"}
        if event_type == "workflow.attempt_started":
            attempt = owner.durable_storage.list_task_attempts(run_id=run_id)[-1]
            assert attempt["status"] == "running"
        if event_type == "workflow.attempt_stream_event":
            rows = owner.get_execution_events(workflow_run_id=run_id)
            assert rows[-1]["raw_digest"] == payload["raw_digest"]
            assert payload["native_event_type"] == "multiagent_node_stream"
            assert payload["node_id"] == "nested-node"
            assert "raw_event" not in payload
        if event_type == "workflow.attempt_completed":
            attempt = owner.durable_storage.list_task_attempts(run_id=run_id)[-1]
            assert attempt["status"] == payload["status"]
        if event_type in {
            "workflow.step_transition", "workflow.run_succeeded",
            "workflow.run_failed", "workflow.run_cancelled",
        }:
            assert run.status == payload["status"]
        seen.append(event_type)

    monkeypatch.setattr(
        "factory.workflow.runtime.event_emitter._get_invoker", lambda: publish,
    )


def _run(tmp_path: Path, monkeypatch, output: dict):
    seen, holder = [], {}
    invoker = StreamingInvoker(output)
    owner = runtime(tmp_path, invoker)
    invoker.owner = holder["owner"] = owner
    _capture(monkeypatch, holder, seen)
    return start(owner), seen


def test_success_live_events_are_canonical_and_post_commit(tmp_path, monkeypatch) -> None:
    result, seen = _run(tmp_path, monkeypatch, {
        "status": "completed", "result": {"value": 1},
    })
    assert result["status"] == "succeeded"
    assert seen == [
        "workflow.run_started", "workflow.attempt_started",
        "workflow.attempt_stream_event", "workflow.attempt_completed",
        "workflow.step_transition", "workflow.run_succeeded",
    ]


def test_failure_live_events_are_canonical_and_post_commit(tmp_path, monkeypatch) -> None:
    result, seen = _run(tmp_path, monkeypatch, {
        "status": "failed", "error": "invalid manifest", "retryable": False,
    })
    assert result["status"] == "failed"
    assert seen == [
        "workflow.run_started", "workflow.attempt_started",
        "workflow.attempt_stream_event", "workflow.attempt_completed",
        "workflow.step_transition", "workflow.run_failed",
    ]


def test_cancel_live_event_follows_run_and_attempt_fences(tmp_path, monkeypatch) -> None:
    seen, holder = [], {}
    invoker = BlockingInvoker()
    owner = runtime(tmp_path, invoker)
    holder["owner"] = owner
    _capture(monkeypatch, holder, seen)
    result, errors = {}, []

    def launch() -> None:
        try:
            result.update(start(owner))
        except BaseException as exc:
            errors.append(exc)

    thread = threading.Thread(target=launch)
    thread.start()
    assert invoker.started.wait(timeout=5)
    record = owner.durable_storage.get_run_by_key(run_key="key")
    cancelled = owner.cancel_run(
        run_id=record.run_id, reason="stop",
        envelope=Envelope(tenant_id="tenant"),
    )
    invoker.release.set()
    thread.join(timeout=5)
    assert errors == [] and result["status"] == cancelled["status"] == "cancelled"
    assert seen == [
        "workflow.run_started", "workflow.attempt_started",
        "workflow.run_cancelled",
    ]
    assert not any(name.startswith("workflow.run.") for name in seen)
