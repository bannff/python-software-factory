"""SQLite DDL for durable named-MCP workflow execution."""
from __future__ import annotations

import hashlib
import sqlite3


_EVENT_COLUMNS = (
    "attempt_id", "revision", "sequence", "run_id", "engine_id",
    "registration_digest", "request_digest", "provider_request_digest",
    "raw_digest", "terminal", "raw_json", "safe_metadata_json", "created_at",
)


def _add_columns(conn: sqlite3.Connection, table: str, columns: dict[str, str]) -> None:
    present = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
    for name, declaration in columns.items():
        if name not in present:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {declaration}")


def _project_legacy_events(conn: sqlite3.Connection) -> None:
    """Project retired rows once, rejecting corrupt or divergent durable evidence."""
    legacy = conn.execute(
        "SELECT attempt_id,revision,sequence,run_id,manifest_digest,raw_digest,"
        "terminal,raw_json,created_at FROM managed_graph_events"
    ).fetchall()
    for row in legacy:
        identity = (row["attempt_id"], row["revision"], row["sequence"])
        digest = hashlib.sha256(row["raw_json"].encode()).hexdigest()
        if row["raw_digest"] != digest:
            raise ValueError(f"legacy event raw_digest mismatch for {identity}")
        projected = (
            row["attempt_id"], row["revision"], row["sequence"], row["run_id"],
            "legacy-v1", row["manifest_digest"], row["manifest_digest"],
            row["manifest_digest"], row["raw_digest"], row["terminal"],
            row["raw_json"], "{}", row["created_at"],
        )
        existing = conn.execute(
            "SELECT " + ",".join(_EVENT_COLUMNS) + " FROM execution_events "
            "WHERE attempt_id=? AND revision=? AND sequence=?", identity,
        ).fetchone()
        if existing is None:
            conn.execute(
                "INSERT INTO execution_events(" + ",".join(_EVENT_COLUMNS) + ") "
                "VALUES(" + ",".join("?" for _ in _EVENT_COLUMNS) + ")",
                projected,
            )
        elif tuple(existing[column] for column in _EVENT_COLUMNS) != projected:
            raise ValueError(f"legacy event projection conflict for {identity}")


def init_task_schema(conn: sqlite3.Connection) -> None:
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS workflow_versions (
      version_id TEXT PRIMARY KEY, workflow_id TEXT NOT NULL,
      declared_version INTEGER NOT NULL, snapshot_json TEXT NOT NULL,
      snapshot_sha256 TEXT NOT NULL,
      UNIQUE(workflow_id, declared_version)
    );
    CREATE TABLE IF NOT EXISTS step_executions (
      step_execution_id TEXT PRIMARY KEY, run_id TEXT NOT NULL,
      workflow_version_id TEXT NOT NULL, step_id TEXT NOT NULL,
      status TEXT NOT NULL, input_json TEXT NOT NULL,
      output_json TEXT, output_digest TEXT, artifact_refs_json TEXT,
      evidence_json TEXT, error TEXT,
      UNIQUE(run_id, step_id),
      FOREIGN KEY(run_id) REFERENCES runs(run_id) ON DELETE CASCADE,
      FOREIGN KEY(workflow_version_id) REFERENCES workflow_versions(version_id)
    );
    CREATE TABLE IF NOT EXISTS task_attempts (
      attempt_id TEXT PRIMARY KEY, step_execution_id TEXT NOT NULL,
      attempt_number INTEGER NOT NULL, status TEXT NOT NULL,
      lease_token TEXT, lease_expires_at TEXT, revision INTEGER NOT NULL DEFAULT 0,
      input_json TEXT NOT NULL, output_json TEXT, envelope_json TEXT,
      evidence_json TEXT, output_digest TEXT, envelope_digest TEXT,
      evidence_digest TEXT, error TEXT, retry_approved INTEGER NOT NULL DEFAULT 0,
      UNIQUE(step_execution_id, attempt_number),
      FOREIGN KEY(step_execution_id) REFERENCES step_executions(step_execution_id)
    );
    CREATE TABLE IF NOT EXISTS managed_graph_events (
      attempt_id TEXT NOT NULL, revision INTEGER NOT NULL,
      sequence INTEGER NOT NULL, run_id TEXT NOT NULL,
      manifest_digest TEXT NOT NULL, raw_digest TEXT NOT NULL,
      terminal INTEGER NOT NULL, raw_json TEXT NOT NULL,
      created_at TEXT NOT NULL,
      PRIMARY KEY(attempt_id,revision,sequence),
      FOREIGN KEY(attempt_id) REFERENCES task_attempts(attempt_id)
    );
    CREATE UNIQUE INDEX IF NOT EXISTS idx_managed_terminal
      ON managed_graph_events(attempt_id,revision) WHERE terminal=1;
    CREATE TABLE IF NOT EXISTS execution_events (
      attempt_id TEXT NOT NULL, revision INTEGER NOT NULL, sequence INTEGER NOT NULL,
      run_id TEXT NOT NULL, engine_id TEXT NOT NULL, registration_digest TEXT NOT NULL,
      request_digest TEXT NOT NULL, provider_request_digest TEXT NOT NULL,
      raw_digest TEXT NOT NULL, terminal INTEGER NOT NULL, raw_json TEXT NOT NULL,
      safe_metadata_json TEXT NOT NULL, created_at TEXT NOT NULL,
      PRIMARY KEY(attempt_id,revision,sequence),
      FOREIGN KEY(attempt_id) REFERENCES task_attempts(attempt_id)
    );
    CREATE UNIQUE INDEX IF NOT EXISTS idx_execution_terminal
      ON execution_events(attempt_id,revision) WHERE terminal=1;
    """)
    _add_columns(conn, "runs", {
        "workflow_version_id": "TEXT", "run_execution_id": "TEXT",
        "run_key": "TEXT", "revision": "INTEGER NOT NULL DEFAULT 0",
    })
    _add_columns(conn, "task_attempts", {
        "envelope_digest": "TEXT", "evidence_digest": "TEXT",
    })
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_runs_named_key "
        "ON runs(run_key) WHERE run_key IS NOT NULL"
    )
    # Additive one-way storage migration for the retired graph-event table.
    # The caller's connection context makes the full projection atomic.
    _project_legacy_events(conn)
