"""Workflow-owned cancellation fences for managed graph attempts."""
from __future__ import annotations

from pathlib import Path

import pytest
from factory.workflow.runtime.envelope import Envelope
from factory.workflow.runtime.runtime import WorkflowRuntime

from .test_managed_graph import DIGEST, GraphInvoker, runtime, start


class CancellingGraphInvoker(GraphInvoker):
    owner: WorkflowRuntime
    cancellation: dict | None = None

    def invoke(self, **kwargs):
        if kwargs["target"].tool_name == "execute_strands_graph_attempt":
            record = self.owner.durable_storage.get_run_by_key(run_key="key")
            self.cancellation = self.owner.cancel_run(
                run_id=record.run_id, reason="concurrent cancellation",
                envelope=Envelope(tenant_id="tenant"),
            )
        return super().invoke(**kwargs)


def test_cancellation_revision_fences_late_managed_completion(tmp_path: Path) -> None:
    invoker = CancellingGraphInvoker()
    owner = runtime(tmp_path, invoker)
    invoker.owner = owner
    result = start(owner)
    attempt = owner.durable_storage.list_task_attempts(run_id=result["run_id"])[0]
    assert result["status"] == attempt["status"] == "cancelled"
    assert attempt["revision"] == 2


def test_cancellation_signals_exact_managed_attempt(tmp_path: Path) -> None:
    invoker = CancellingGraphInvoker()
    owner = runtime(tmp_path, invoker)
    invoker.owner = owner
    result = start(owner)
    target, arguments, key, _ = next(
        call for call in invoker.calls
        if call[0].tool_name == "cancel_strands_graph_attempt"
    )
    assert (target.brick_name, target.tool_name) == (
        "agent", "cancel_strands_graph_attempt",
    )
    assert arguments == {
        "workflow_run_id": result["run_id"], "attempt_id": result["attempt_id"],
        "revision": 1, "engine_id": result["engine_id"],
        "registration_digest": result["registration_digest"],
        "request_digest": result["request_digest"],
        "provider_request_digest": DIGEST,
    }
    assert key == f"cancel:{result['attempt_id']}:r1"
    assert invoker.cancellation["cancellation"] == {
        "outcome": "cancel_requested", "attempt_id": result["attempt_id"],
        "revision": 1,
    }


@pytest.mark.parametrize(
    ("cancel_outcome", "cancel_raises", "expected"),
    [("not_owner", False, "not_owner"),
     ("cancel_requested", True, "transport_error")],
)
def test_agent_signal_miss_never_undoes_durable_cancellation(
    tmp_path: Path, cancel_outcome: str, cancel_raises: bool, expected: str,
) -> None:
    invoker = CancellingGraphInvoker(
        cancel_outcome=cancel_outcome, cancel_raises=cancel_raises,
    )
    owner = runtime(tmp_path, invoker)
    invoker.owner = owner
    result = start(owner)
    assert result["status"] == "cancelled"
    assert invoker.cancellation["status"] == "cancelled"
    assert invoker.cancellation["cancellation"]["outcome"] == expected
    attempt = owner.durable_storage.list_task_attempts(run_id=result["run_id"])[0]
    assert attempt["status"] == "cancelled" and attempt["revision"] == 2
