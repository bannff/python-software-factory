"""Canary coverage for protected Workflow error persistence."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from factory.workflow.runtime.envelope import Envelope
from factory.workflow.runtime.storage.sqlite import SqliteWorkflowStorage


def test_update_run_redacts_protected_error_before_sqlite_persistence(tmp_path) -> None:
    storage = SqliteWorkflowStorage(tmp_path / "workflow.db")
    storage.init_schema()
    now = datetime.now(timezone.utc)
    storage.create_run(
        run_id="run-1", workflow_id="workflow-1", workflow_version=1,
        tenant_id=None, input={}, envelope=Envelope(), now=now,
    )
    canary = "workflow-sqlite-protected@example.test"
    record = storage.update_run(
        run_id="run-1", status="failed", current_step_id=None,
        waiting_for_event_type=None, last_event_id=None, result=None,
        error=f"body={canary}", now=now,
    )

    with sqlite3.connect(storage.path) as connection:
        persisted = connection.execute(
            "SELECT error FROM runs WHERE run_id=?", ("run-1",)
        ).fetchone()[0]
    assert record.error == persisted == "body=[protected]"
    assert canary not in persisted
