"""SQLite storage backend for workflow runs, events, and named tasks."""
from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from factory.workflow.runtime.envelope import Envelope
from factory.workflow.runtime.models import EventRecord, RunRecord
from . import events as events_ops
from . import runs as runs_ops
from .loop_schema import init_loop_schema
from .loop_storage_mixin import LoopStorageMixin
from .task_schema import init_task_schema
from .task_storage_mixin import DurableTaskStorageMixin


class SqliteWorkflowStorage(LoopStorageMixin, DurableTaskStorageMixin):
    def __init__(self, path: Path):
        self.path = path

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY, tenant_id TEXT,
                    workflow_id TEXT NOT NULL, workflow_version INTEGER NOT NULL,
                    status TEXT NOT NULL, current_step_id TEXT,
                    waiting_for_event_type TEXT, last_event_id INTEGER NOT NULL DEFAULT 0,
                    started_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                    input_json TEXT NOT NULL, result_json TEXT, error TEXT,
                    envelope_json TEXT NOT NULL
                )
            """)
            try:
                conn.execute("ALTER TABLE runs ADD COLUMN last_event_id INTEGER NOT NULL DEFAULT 0")
            except sqlite3.OperationalError:
                pass
            conn.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL,
                    event_type TEXT NOT NULL, payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL, envelope_json TEXT NOT NULL,
                    FOREIGN KEY(run_id) REFERENCES runs(run_id) ON DELETE CASCADE
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_events_run_id ON events(run_id,id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_runs_updated ON runs(updated_at DESC,run_id DESC)")
            init_task_schema(conn)
            init_loop_schema(conn)

    def health_check(self) -> dict[str, Any]:
        try:
            with self._connect() as conn:
                conn.execute("SELECT 1")
            return {"ok": True, "backend": "sqlite", "path": str(self.path),
                    "durable_named_mcp": True}
        except Exception as exc:
            return {"ok": False, "backend": "sqlite", "path": str(self.path),
                    "durable_named_mcp": False, "error": str(exc)}

    def create_run(
        self, *, run_id: str, workflow_id: str, workflow_version: int,
        tenant_id: str | None, input: dict[str, Any], envelope: Envelope, now: datetime,
        run_key: str | None = None,
        workflow_version_id: str | None = None,
        run_execution_id: str | None = None,
    ) -> RunRecord:
        return runs_ops.create_run(
            self._connect, self.get_run, self.get_run_by_key,
            run_id=run_id, run_key=run_key, workflow_id=workflow_id,
            workflow_version=workflow_version, tenant_id=tenant_id, input=input,
            envelope=envelope, now=now, workflow_version_id=workflow_version_id,
            run_execution_id=run_execution_id,
        )

    def get_run(self, *, run_id: str) -> RunRecord | None:
        return runs_ops.get_run(self._connect, run_id=run_id)

    def update_run(
        self, *, run_id: str, status: str, current_step_id: str | None,
        waiting_for_event_type: str | None, last_event_id: int | None,
        result: dict[str, Any] | None, error: str | None, now: datetime,
        expected_statuses: set[str] | None = None,
        expected_revision: int | None = None,
    ) -> RunRecord:
        return runs_ops.update_run(
            self._connect, self.get_run, run_id=run_id, status=status,
            current_step_id=current_step_id,
            waiting_for_event_type=waiting_for_event_type,
            last_event_id=last_event_id, result=result, error=error, now=now,
            expected_statuses=expected_statuses, expected_revision=expected_revision,
        )

    def list_runs(
        self, *, tenant_id: str | None, workflow_id: str | None,
        status: str | None, limit: int, cursor: str | None,
    ) -> tuple[list[RunRecord], str | None]:
        return runs_ops.list_runs(
            self._connect, tenant_id=tenant_id, workflow_id=workflow_id,
            status=status, limit=limit, cursor=cursor,
        )

    def append_event(
        self, *, run_id: str, event_type: str, payload: dict[str, Any],
        envelope: Envelope, now: datetime,
    ) -> EventRecord:
        return events_ops.append_event(
            self._connect, run_id=run_id, event_type=event_type,
            payload=payload, envelope=envelope, now=now,
        )

    def get_events_since(self, *, run_id: str, after_event_id: int) -> list[EventRecord]:
        return events_ops.get_events_since(self._connect, run_id=run_id, after_event_id=after_event_id)

    def get_last_event_id(self, *, run_id: str) -> int:
        return events_ops.get_last_event_id(self._connect, run_id=run_id)
