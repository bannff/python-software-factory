"""Managed graph retry, lease recovery, and restart authority."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from factory.workflow.runtime.envelope import Envelope
from factory.workflow.runtime.execution.adapters import create_executor
from factory.workflow.runtime.models import Settings
from factory.workflow.runtime.runtime import WorkflowRuntime
from factory.workflow.runtime.storage.sqlite import SqliteWorkflowStorage

from .test_managed_graph import DIGEST, GraphInvoker, runtime, start


class RetryInvoker(GraphInvoker):
    def __init__(self, *, transport_error: bool = False) -> None:
        super().__init__()
        self.transport_error = transport_error
        self.invocations = 0

    def invoke(self, **kwargs):
        if kwargs["target"].tool_name == "cancel_strands_graph_attempt":
            return super().invoke(**kwargs)
        self.invocations += 1
        if self.invocations == 1 and self.transport_error:
            self.calls.append((
                kwargs["target"], kwargs["arguments"],
                kwargs["idempotency_key"], kwargs["envelope"],
            ))
            self.bindings.append(kwargs.get("attempt"))
            raise ConnectionError("temporary Agent transport unavailable")
        self.output = (
            {"status": "failed", "error": "execution unavailable", "retryable": True}
            if self.invocations == 1
            else {"status": "completed", "result": {"value": 7}}
        )
        return super().invoke(**kwargs)


@pytest.mark.parametrize("transport_error", [False, True])
def test_retry_uses_new_attempt_over_identical_frozen_descriptor(
    tmp_path: Path, transport_error: bool,
) -> None:
    invoker = RetryInvoker(transport_error=transport_error)
    owner = runtime(tmp_path, invoker)
    result = start(owner)
    attempts = owner.durable_storage.list_task_attempts(run_id=result["run_id"])
    assert result["status"] == "succeeded"
    assert [row["attempt_number"] for row in attempts] == [1, 2]
    assert attempts[0]["attempt_id"] != attempts[1]["attempt_id"]
    calls = [call for call in invoker.calls if call[0].tool_name == "execute_strands_graph_attempt"]
    assert [call[2] for call in calls] == [row["attempt_id"] for row in attempts]
    assert calls[0][1]["request"] == calls[1][1]["request"]
    assert calls[0][1]["provider_request_digest"] == calls[1][1]["provider_request_digest"] == DIGEST
    assert [binding["revision"] for binding in invoker.bindings] == [1, 1]


def test_preparation_failure_is_terminal_under_fixed_policy(tmp_path: Path) -> None:
    invoker = GraphInvoker({
        "status": "failed", "error": "manifest validation failed",
        "retryable": False,
    })
    owner = runtime(tmp_path, invoker)
    result = start(owner)
    attempts = owner.durable_storage.list_task_attempts(run_id=result["run_id"])
    assert result["status"] == "failed"
    assert len(attempts) == len(invoker.calls) == 1
    assert attempts[0]["retry_approved"] == 0


class ProcessCrash(BaseException):
    pass


class CrashInvoker(GraphInvoker):
    def invoke(self, **kwargs):
        if kwargs["target"].tool_name == "execute_strands_graph_attempt":
            self.calls.append((
                kwargs["target"], kwargs["arguments"],
                kwargs["idempotency_key"], kwargs["envelope"],
            ))
            self.bindings.append(kwargs.get("attempt"))
            raise ProcessCrash("worker stopped after claim")
        return super().invoke(**kwargs)


def test_restart_reclaims_same_attempt_with_incremented_revision(tmp_path: Path) -> None:
    crashing = CrashInvoker()
    owner = runtime(tmp_path, crashing)
    with pytest.raises(ProcessCrash):
        start(owner)
    record = owner.durable_storage.get_run_by_key(run_key="key")
    before = owner.durable_storage.list_task_attempts(run_id=record.run_id)[0]
    database = tmp_path / "config" / "state.db"
    with sqlite3.connect(database) as conn:
        conn.execute(
            "UPDATE task_attempts SET lease_expires_at=? WHERE attempt_id=?",
            ("1970-01-01T00:00:00+00:00", before["attempt_id"]),
        )

    resumed_invoker = GraphInvoker()
    storage = SqliteWorkflowStorage(database)
    storage.init_schema()
    settings = Settings()
    restarted = WorkflowRuntime(
        config_dir=tmp_path / "config", settings=settings,
        settings_raw=settings.model_dump(), workflows=[], storage=storage,
        executor=create_executor(), tool_invoker=resumed_invoker,
    )
    resumed = restarted.resume_run(
        run_id=record.run_id, envelope=Envelope(tenant_id="tenant"),
    )
    after = restarted.durable_storage.list_task_attempts(run_id=record.run_id)
    assert resumed["status"] == "succeeded" and len(after) == 1
    assert after[0]["attempt_id"] == before["attempt_id"]
    assert before["revision"] == 1 and after[0]["revision"] == 2
    assert crashing.calls[0][2] == resumed_invoker.calls[0][2] == before["attempt_id"]
    assert crashing.calls[0][1]["request"] == resumed_invoker.calls[0][1]["request"]
    assert resumed_invoker.bindings[0]["revision"] == 2
