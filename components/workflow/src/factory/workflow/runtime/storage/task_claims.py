"""Transactional claim and exact attempt-argument binding."""
from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timedelta
from typing import Any

from factory.workflow.runtime.attempt_binding import (
    expected_attempt_binding, verify_attempt_binding,
)
from factory.workflow.runtime.canonical import canonical_json, canonical_loads
from factory.workflow.runtime.run_binding import DurableAttemptBindingError
from factory.workflow.runtime.task_ids import step_execution_id
from factory.workflow.runtime.task_models import AttemptClaim


class ContinuationLimitError(ValueError):
    """A frozen Workflow continuation cap was exhausted."""


def _claim_from(row: sqlite3.Row, status: str | None = None) -> AttemptClaim:
    return AttemptClaim(
        attempt_id=row["attempt_id"], step_execution_id=row["step_execution_id"],
        attempt_number=row["attempt_number"], revision=row["revision"],
        status=status or row["status"], lease_token=row["lease_token"],
        canonical_input=row["input_json"],
        output=canonical_loads(row["output_json"])
        if row["output_json"] is not None else None,
        error=row["error"],
    )


def _insert_attempt(
    conn: sqlite3.Connection, step_exec: str, number: int,
    base_input: str, idempotency_argument: str | None,
) -> sqlite3.Row:
    attempt_id, input_json = expected_attempt_binding(
        step_execution_id=step_exec, attempt_number=number,
        step_input_json=base_input, idempotency_argument=idempotency_argument,
    )
    conn.execute(
        "INSERT INTO task_attempts"
        "(attempt_id,step_execution_id,attempt_number,status,input_json) "
        "VALUES(?,?,?,'pending',?)",
        (attempt_id, step_exec, number, input_json),
    )
    return conn.execute(
        "SELECT * FROM task_attempts WHERE attempt_id=?", (attempt_id,),
    ).fetchone()


def _verify_existing(
    rows: list[sqlite3.Row], *, step_exec: str, step_input: str,
    idempotency_argument: str | None,
) -> None:
    for expected_number, row in enumerate(rows, start=1):
        if row["step_execution_id"] != step_exec:
            raise DurableAttemptBindingError(
                "durable attempt step_execution_id binding mismatch"
            )
        verify_attempt_binding(
            step_execution_id=step_exec,
            attempt_number=row["attempt_number"], attempt_id=row["attempt_id"],
            attempt_input_json=row["input_json"], step_input_json=step_input,
            idempotency_argument=idempotency_argument,
            expected_number=expected_number,
        )


def admit(
    connect: Any, *, run_id: str, run_execution_id: str,
    workflow_version_id: str, step_id: str, inputs: dict[str, Any],
    idempotency_argument: str | None = None,
) -> AttemptClaim:
    """Persist one deterministic pending attempt without claiming its lease."""
    base_input = canonical_json(inputs)
    step_exec = step_execution_id(run_execution_id, step_id)
    with connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        run = conn.execute(
            "SELECT status FROM runs WHERE run_id=?", (run_id,),
        ).fetchone()
        if run is None or run["status"] in {"failed", "cancelled", "succeeded"}:
            raise ValueError("run is not active")
        conn.execute(
            "INSERT OR IGNORE INTO step_executions"
            "(step_execution_id,run_id,workflow_version_id,step_id,status,input_json) "
            "VALUES(?,?,?,?,'pending',?)",
            (step_exec, run_id, workflow_version_id, step_id, base_input),
        )
        step = conn.execute(
            "SELECT * FROM step_executions WHERE step_execution_id=?", (step_exec,),
        ).fetchone()
        if step["input_json"] != base_input or step["run_id"] != run_id \
                or step["workflow_version_id"] != workflow_version_id \
                or step["step_id"] != step_id:
            raise DurableAttemptBindingError("step execution binding conflict")
        rows = conn.execute(
            "SELECT * FROM task_attempts WHERE step_execution_id=? "
            "ORDER BY attempt_number", (step_exec,),
        ).fetchall()
        _verify_existing(
            rows, step_exec=step_exec, step_input=step["input_json"],
            idempotency_argument=idempotency_argument,
        )
        row = rows[-1] if rows else _insert_attempt(
            conn, step_exec, 1, step["input_json"], idempotency_argument,
        )
        return _claim_from(row)


def claim(
    connect: Any, *, run_id: str, run_execution_id: str,
    workflow_version_id: str, step_id: str, inputs: dict[str, Any],
    max_attempts: int, max_continuations: int, lease_seconds: int, now: datetime,
    idempotency_argument: str | None = None,
) -> AttemptClaim:
    base_input = canonical_json(inputs)
    step_exec = step_execution_id(run_execution_id, step_id)
    token = uuid.uuid4().hex
    expiry = (now + timedelta(seconds=lease_seconds)).isoformat()
    with connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        run = conn.execute(
            "SELECT status FROM runs WHERE run_id=?", (run_id,),
        ).fetchone()
        if run is None or run["status"] in {"failed", "cancelled", "succeeded"}:
            raise ValueError("run is not active")
        conn.execute(
            "INSERT OR IGNORE INTO step_executions"
            "(step_execution_id,run_id,workflow_version_id,step_id,status,input_json) "
            "VALUES(?,?,?,?,'pending',?)",
            (step_exec, run_id, workflow_version_id, step_id, base_input),
        )
        step = conn.execute(
            "SELECT * FROM step_executions WHERE step_execution_id=?", (step_exec,),
        ).fetchone()
        if step["input_json"] != base_input or step["run_id"] != run_id \
                or step["workflow_version_id"] != workflow_version_id \
                or step["step_id"] != step_id:
            raise DurableAttemptBindingError("step execution binding conflict")
        rows = conn.execute(
            "SELECT * FROM task_attempts WHERE step_execution_id=? "
            "ORDER BY attempt_number", (step_exec,),
        ).fetchall()
        _verify_existing(
            rows, step_exec=step_exec, step_input=step["input_json"],
            idempotency_argument=idempotency_argument,
        )
        row = rows[-1] if rows else None
        if row is None:
            row = _insert_attempt(
                conn, step_exec, 1, step["input_json"], idempotency_argument,
            )
        elif row["status"] == "continued":
            continuations = sum(item["status"] == "continued" for item in rows)
            if continuations >= max_continuations:
                raise ContinuationLimitError("continuation limit exceeded")
            row = _insert_attempt(
                conn, step_exec, row["attempt_number"] + 1,
                step["input_json"], idempotency_argument,
            )
        elif row["status"] == "failed" and row["retry_approved"]:
            failures = sum(item["status"] == "failed" for item in rows)
            if failures >= max_attempts:
                raise ValueError("retry approval exceeds policy")
            row = _insert_attempt(
                conn, step_exec, row["attempt_number"] + 1,
                step["input_json"], idempotency_argument,
            )
        elif row["status"] in {"succeeded", "failed", "cancelled"}:
            return _claim_from(row)
        elif row["status"] == "running" \
                and row["lease_expires_at"] > now.isoformat():
            return _claim_from(row, "busy")
        revision = row["revision"]
        updated = conn.execute(
            "UPDATE task_attempts SET status='running',lease_token=?,"
            "lease_expires_at=?,revision=revision+1 WHERE attempt_id=? "
            "AND revision=? AND status IN ('pending','running')",
            (token, expiry, row["attempt_id"], revision),
        )
        if updated.rowcount != 1:
            raise ValueError("task attempt claim lost")
        conn.execute(
            "UPDATE step_executions SET status='running' "
            "WHERE step_execution_id=?", (step_exec,),
        )
        claimed = conn.execute(
            "SELECT * FROM task_attempts WHERE attempt_id=?", (row["attempt_id"],),
        ).fetchone()
        return _claim_from(claimed)
