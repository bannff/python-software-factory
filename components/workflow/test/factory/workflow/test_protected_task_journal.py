"""Protected task-journal and execution-event persistence canaries."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest

from factory.workflow.runtime.envelope import Envelope
from .test_task_journal import _run, _storage


def test_protected_failure_is_generic_across_attempt_step_event_sinks(
    tmp_path: Path, monkeypatch,
) -> None:
    storage = _storage(tmp_path / "protected-failure.db")
    workflow, run = _run(storage)
    claim = storage.claim_task(
        run=run, step=workflow.steps[0], inputs={}, now=datetime.now(timezone.utc),
    )
    canary = "workflow-protected-error@example.test"
    storage.fail_task(
        attempt_id=claim.attempt_id, revision=claim.revision,
        lease_token=claim.lease_token or "", error=f"provider body {canary}",
        envelope={"ok": False, "error": {
            "type": "TimeoutError", "message": canary,
        }}, retryable=True, max_attempts=2, protected=True,
    )
    storage.append_event(
        run_id=run.run_id, event_type="workflow.failed",
        payload={"artifact_ref": "pc_v1_abcdefghijklmnopqrstuv", "error": canary},
        envelope=Envelope(), now=datetime.now(timezone.utc),
    )

    with sqlite3.connect(storage.path) as connection:
        attempt_error, step_error, envelope_json, event_json = connection.execute(
            "SELECT a.error,s.error,a.envelope_json,e.payload_json "
            "FROM task_attempts a JOIN step_executions s USING(step_execution_id) "
            "JOIN events e ON e.run_id=s.run_id WHERE a.attempt_id=?",
            (claim.attempt_id,),
        ).fetchone()
    assert canary not in str((attempt_error, step_error, envelope_json, event_json))
    assert attempt_error == step_error == "protected-operation-failed"

    from factory.workflow.runtime.execution.steps import task_events
    emitted: list[dict] = []
    monkeypatch.setattr(
        task_events, "emit_workflow_event",
        lambda _, payload, *__: emitted.append(payload),
    )
    task_events.completed(
        run, workflow.steps[0], claim, status="failed", error=canary, protected=True,
    )
    assert canary not in str(emitted)
    assert emitted[0]["error"] == "protected-operation-failed"


def test_unmarked_raw_evidence_and_aliases_are_rejected_before_execution_event_write(
    tmp_path: Path,
) -> None:
    storage = _storage(tmp_path / "raw-evidence.db")
    now = datetime.now(timezone.utc)
    for field in (
        "body", "subject", "recipients", "to", "cc", "bcc", "html", "text",
        "message", "query", "provider_request", "provider_response",
        "attachments", "raw_evidence",
    ):
        with pytest.raises(ValueError, match="protected inline content"):
            storage.append_execution_event(
                workflow_run_id="missing", attempt_id="missing", revision=1,
                engine_id="engine", registration_digest="a" * 64,
                request_digest="b" * 64, provider_request_digest="c" * 64,
                sequence=0, terminal=False,
                raw_evidence={field: "raw-evidence-canary@example.test"},
                safe_metadata={}, now=now,
            )
