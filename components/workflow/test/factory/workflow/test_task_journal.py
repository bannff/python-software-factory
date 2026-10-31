"""SQLite journal CAS, reclaim, retry, and immutable snapshot tests."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3

import pytest

from factory.workflow.runtime.envelope import Envelope
from factory.workflow.runtime.models import (
    StepDefinition, ToolTarget, WorkflowDefinition,
)
from factory.workflow.runtime.storage.sqlite import SqliteWorkflowStorage
from factory.workflow.runtime.task_ids import workflow_run_id


def _workflow(payload=None, max_attempts=2, **updates):
    return WorkflowDefinition(
        id="wf", name="Workflow", version=1,
        steps=[StepDefinition(
            id="task", kind="task", task_mode="named_mcp", task_type="work",
            tool_target=ToolTarget(brick_name="demo", tool_name="work"),
            task_payload=payload or {}, max_attempts=max_attempts, lease_seconds=1,
            **updates,
        )],
    )


def _run(storage, workflow=None):
    workflow = workflow or _workflow()
    version = storage.persist_workflow_version(workflow)
    execution = workflow_run_id(version, "run", {"x": 1})
    run = storage.create_run(
        run_id=execution, run_key="run", workflow_id="wf", workflow_version=1,
        workflow_version_id=version, run_execution_id=execution,
        tenant_id=None, input={"x": 1}, envelope=Envelope(),
        now=datetime.now(timezone.utc),
    )
    return workflow, run


def _storage(path: Path):
    storage = SqliteWorkflowStorage(path)
    storage.init_schema()
    return storage


def test_reclaim_reuses_attempt_and_fences_stale_completion(tmp_path: Path) -> None:
    path = tmp_path / "journal.db"
    workflow, run = _run(_storage(path))
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    first = _storage(path).claim_task(
        run=run, step=workflow.steps[0], inputs={"x": 1}, now=now,
    )
    busy = _storage(path).claim_task(
        run=run, step=workflow.steps[0], inputs={"x": 1},
        now=now + timedelta(milliseconds=500),
    )
    reclaimed = _storage(path).claim_task(
        run=run, step=workflow.steps[0], inputs={"x": 1},
        now=now + timedelta(seconds=2),
    )
    assert busy.status == "busy"
    assert reclaimed.attempt_id == first.attempt_id
    assert reclaimed.attempt_number == 1
    assert reclaimed.lease_token != first.lease_token
    with pytest.raises(ValueError, match="stale"):
        _storage(path).fail_task(
            attempt_id=first.attempt_id, revision=first.revision,
            lease_token=first.lease_token or "", error="same-error",
            envelope={"ok": False}, retryable=False, max_attempts=2,
        )
    with pytest.raises(ValueError, match="stale"):
        _storage(path).complete_task(
            attempt_id=first.attempt_id, revision=first.revision,
            lease_token=first.lease_token or "",
            output={"value": 1}, envelope={"ok": True}, evidence={},
        )
    assert _storage(path).complete_task(
        attempt_id=reclaimed.attempt_id, revision=reclaimed.revision,
        lease_token=reclaimed.lease_token or "", output={"value": 1},
        envelope={"ok": True}, evidence={},
    )
    assert not _storage(path).complete_task(
        attempt_id=reclaimed.attempt_id, revision=reclaimed.revision,
        lease_token=reclaimed.lease_token or "", output={"value": 1},
        envelope={"ok": True}, evidence={},
    )
    with pytest.raises(ValueError, match="conflict"):
        _storage(path).complete_task(
            attempt_id=reclaimed.attempt_id, revision=reclaimed.revision,
            lease_token=reclaimed.lease_token or "", output={"value": 2},
            envelope={"ok": True}, evidence={},
        )


def test_retry_number_increments_only_after_approved_terminal_failure(tmp_path: Path) -> None:
    storage = _storage(tmp_path / "retry.db")
    workflow, run = _run(storage)
    now = datetime.now(timezone.utc)
    first = storage.claim_task(run=run, step=workflow.steps[0], inputs={}, now=now)
    assert storage.fail_task(
        attempt_id=first.attempt_id, revision=first.revision,
        lease_token=first.lease_token or "",
        error="transport", envelope={"ok": False}, retryable=True, max_attempts=2,
    )
    second = _storage(storage.path).claim_task(
        run=run, step=workflow.steps[0], inputs={}, now=now,
    )
    assert second.attempt_number == 2
    assert second.attempt_id != first.attempt_id
    assert not storage.fail_task(
        attempt_id=second.attempt_id, revision=second.revision,
        lease_token=second.lease_token or "",
        error="transport", envelope={"ok": False}, retryable=True, max_attempts=2,
    )
    terminal = storage.claim_task(run=run, step=workflow.steps[0], inputs={}, now=now)
    assert terminal.status == "failed" and terminal.attempt_number == 2


def test_workflow_version_conflict_is_loud_and_snapshot_exact(tmp_path: Path) -> None:
    storage = _storage(tmp_path / "versions.db")
    original = _workflow({"value": "original"})
    version = storage.persist_workflow_version(original)
    assert storage.load_workflow_version(version) == original
    changed = _workflow({"value": "changed"})
    with pytest.raises(ValueError, match="workflow-version conflict"):
        storage.persist_workflow_version(changed)


def test_artifact_bound_snapshot_keeps_continuation_vocabulary(tmp_path: Path) -> None:
    storage = _storage(tmp_path / "protected-snapshot.db")
    workflow = _workflow({"artifact": {"artifact_ref": "pc_v1_abc", "fingerprint": "a" * 64}},
        max_continuations=2, task_outcome={
            "success": {"pointer": "/status", "equals": "ok"},
            "continuation": {"pointer": "/status", "equals": "partial"},
            "retryable": {"pointer": "/retryable", "equals": True}, "error_pointer": "/error"})
    version = storage.persist_workflow_version(workflow)
    assert storage.load_workflow_version(version) == workflow


def test_workflow_snapshot_tamper_is_rejected(tmp_path: Path) -> None:
    storage = _storage(tmp_path / "tamper.db")
    version = storage.persist_workflow_version(_workflow())
    with sqlite3.connect(storage.path) as conn:
        conn.execute(
            "UPDATE workflow_versions SET snapshot_json=? WHERE version_id=?",
            ('{"id":"tampered"}', version),
        )
    with pytest.raises(ValueError, match="integrity"):
        storage.load_workflow_version(version)



def test_task_failure_redacts_error_in_journal_and_event_payload(tmp_path: Path, monkeypatch) -> None:
    storage = _storage(tmp_path / "error.db")
    workflow, run = _run(storage)
    claim = storage.claim_task(run=run, step=workflow.steps[0], inputs={}, now=datetime.now(timezone.utc))
    canary = "journal-secret@example.test"
    storage.fail_task(
        attempt_id=claim.attempt_id, revision=claim.revision,
        lease_token=claim.lease_token or "", error=f"to={canary}",
        envelope={"ok": False, "error": {"message": f"html={canary}"}},
        retryable=False, max_attempts=2,
    )
    rows = storage.list_task_attempts(run_id=run.run_id)
    assert canary not in str(rows)
    from factory.workflow.runtime.execution.steps import task_events
    events: list[dict] = []
    monkeypatch.setattr(task_events, "emit_workflow_event", lambda _, payload, *__: events.append(payload))
    task_events.completed(run, workflow.steps[0], claim, status="failed", error=f"to={canary}")
    assert canary not in str(events)

    storage = _storage(tmp_path / "protected.db")
    artifact = {"artifact_ref": "pc_v1_abcdefghijklmnopqrstuv", "fingerprint": "a" * 64,
                "descriptor": {"classification": "business", "purpose": "email",
                               "tenant_id": "tenant", "owner_principal_id": "owner",
                               "artifact_kind": "email"}}
    protected = {"artifact": artifact, "body": "task-business-canary@example.test"}
    with pytest.raises(ValueError, match="protected inline content"):
        storage.persist_workflow_version(_workflow(protected))
    workflow, run = _run(storage)
    now = datetime.now(timezone.utc)
    with pytest.raises(ValueError, match="protected inline content"):
        storage.claim_task(run=run, step=workflow.steps[0], inputs=protected, now=now)
    claim = storage.claim_task(run=run, step=workflow.steps[0], inputs={}, now=now)
    for field in ("output", "evidence"):
        kwargs = {"output": {"ok": True}, "evidence": {"ok": True}}
        kwargs[field] = protected
        with pytest.raises(ValueError, match="protected inline content"):
            storage.complete_task(attempt_id=claim.attempt_id, revision=claim.revision,
                                  lease_token=claim.lease_token or "", envelope={}, **kwargs)
    with pytest.raises(ValueError, match="protected inline content"):
        storage.append_execution_event(
            workflow_run_id="r", attempt_id="a", revision=1, engine_id="engine",
            registration_digest="a" * 64, request_digest="a" * 64,
            provider_request_digest="a" * 64, sequence=0, terminal=False,
            raw_evidence=protected, safe_metadata={}, now=now,
        )
