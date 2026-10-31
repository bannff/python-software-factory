"""Run storage operations for the SQLite workflow backend."""
from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime
from typing import Any

from pydantic import ValidationError

from factory.workflow.runtime.canonical import canonical_json
from factory.workflow.runtime.envelope import Envelope, FrozenEnvelope
from factory.mcp_utils.interface import sanitize_protected_error
from factory.workflow.runtime.models import RunRecord
from factory.workflow.runtime.run_binding import DurableIntegrityError, verify_durable_run_binding
from .models import PaginationCursor, iso_format, parse_datetime

logger = logging.getLogger(__name__)


def row_to_run(row: sqlite3.Row) -> RunRecord:
    keys = row.keys()
    record = RunRecord(
        run_id=row["run_id"], run_key=row["run_key"] if "run_key" in keys else None,
        tenant_id=row["tenant_id"], workflow_id=row["workflow_id"],
        workflow_version=int(row["workflow_version"]),
        workflow_version_id=row["workflow_version_id"] if "workflow_version_id" in keys else None,
        run_execution_id=row["run_execution_id"] if "run_execution_id" in keys else None,
        revision=int(row["revision"]) if "revision" in keys else 0,
        status=row["status"], current_step_id=row["current_step_id"],
        waiting_for_event_type=row["waiting_for_event_type"],
        last_event_id=int(row["last_event_id"]) if "last_event_id" in keys else 0,
        started_at=parse_datetime(row["started_at"]), updated_at=parse_datetime(row["updated_at"]),
        input=json.loads(row["input_json"]),
        result=json.loads(row["result_json"]) if row["result_json"] else None,
        error=row["error"],
        initiation_envelope=FrozenEnvelope.model_validate_json(row["envelope_json"]),
    )
    verify_durable_run_binding(record)
    return record


def _same_binding(existing: RunRecord, expected: dict[str, Any]) -> bool:
    return (
        existing.run_id == expected["run_id"]
        and existing.run_key == expected["run_key"]
        and existing.workflow_id == expected["workflow_id"]
        and existing.workflow_version == expected["workflow_version"]
        and existing.workflow_version_id == expected["workflow_version_id"]
        and existing.run_execution_id == expected["run_execution_id"]
        and existing.tenant_id == expected["tenant_id"]
        and canonical_json(existing.input) == canonical_json(expected["input"])
    )


def create_run(
    connect_fn: Any, get_run_fn: Any, get_run_by_key_fn: Any, *,
    run_id: str, run_key: str | None, workflow_id: str, workflow_version: int,
    tenant_id: str | None, input: dict[str, Any], envelope: Envelope, now: datetime,
    workflow_version_id: str | None = None, run_execution_id: str | None = None,
) -> RunRecord:
    expected = locals().copy()
    with connect_fn() as conn:
        stamp = iso_format(now)
        try:
            conn.execute(
                "INSERT INTO runs(run_id,run_key,tenant_id,workflow_id,workflow_version,status,"
                "current_step_id,waiting_for_event_type,last_event_id,started_at,updated_at,"
                "input_json,result_json,error,envelope_json,workflow_version_id,run_execution_id) "
                "VALUES(?,?,?,?,?,'running',NULL,NULL,0,?,?,?,?,?,?,?,?)",
                (run_id, run_key, tenant_id, workflow_id, int(workflow_version), stamp, stamp,
                 canonical_json(input), None, None, envelope.model_dump_json(),
                 workflow_version_id, run_execution_id),
            )
        except sqlite3.IntegrityError:
            existing = get_run_by_key_fn(run_key=run_key) if run_key else get_run_fn(run_id=run_id)
            if existing is None:
                raise
            if run_key and not _same_binding(existing, expected):
                raise ValueError("run-key conflict")
            if workflow_version_id and existing.workflow_version_id != workflow_version_id:
                raise ValueError("run workflow-version conflict")
            return existing
    record = get_run_fn(run_id=run_id)
    if record is None:
        raise RuntimeError("failed to create run")
    return record


def get_run(connect_fn: Any, *, run_id: str) -> RunRecord | None:
    with connect_fn() as conn:
        row = conn.execute("SELECT * FROM runs WHERE run_id=?", (run_id,)).fetchone()
    return row_to_run(row) if row else None


def get_run_by_key(connect_fn: Any, *, run_key: str) -> RunRecord | None:
    with connect_fn() as conn:
        row = conn.execute("SELECT * FROM runs WHERE run_key=?", (run_key,)).fetchone()
    return row_to_run(row) if row else None


def update_run(
    connect_fn: Any, get_run_fn: Any, *, run_id: str, status: str,
    current_step_id: str | None, waiting_for_event_type: str | None,
    last_event_id: int | None, result: dict[str, Any] | None, error: str | None,
    now: datetime, expected_statuses: set[str] | None = None,
    expected_revision: int | None = None,
) -> RunRecord:
    safe_error = sanitize_protected_error(error) if error is not None else None
    values: list[Any] = [status, current_step_id, waiting_for_event_type, iso_format(now),
                         canonical_json(result) if result is not None else None, safe_error]
    sets = ["status=?", "current_step_id=?", "waiting_for_event_type=?", "updated_at=?",
            "result_json=?", "error=?", "revision=revision+1"]
    if last_event_id is not None:
        sets.insert(3, "last_event_id=?")
        values.insert(3, int(last_event_id))
    where, tail = ["run_id=?"], [run_id]
    if expected_statuses:
        where.append("status IN (%s)" % ",".join("?" for _ in expected_statuses))
        tail.extend(sorted(expected_statuses))
    if expected_revision is not None:
        where.append("revision=?")
        tail.append(expected_revision)
    with connect_fn() as conn:
        cursor = conn.execute(
            f"UPDATE runs SET {','.join(sets)} WHERE {' AND '.join(where)}", values + tail,
        )
        if (expected_statuses or expected_revision is not None) and cursor.rowcount != 1:
            raise ValueError("stale run transition")
    record = get_run_fn(run_id=run_id)
    if record is None:
        raise RuntimeError("run not found")
    return record


def _row_to_run_lenient(row: sqlite3.Row) -> RunRecord | None:
    """Item 12(b)/(c) (owner smoke #2): a bulk ``list_runs`` must not let
    ONE unreadable row (a Pydantic validation failure, or a durable-binding
    mismatch predating today's stricter checks) crash the whole call —
    every OTHER caller-visible run in the response is real data that must
    still reach the caller. ``get_run``/``get_run_by_key`` stay strict: a
    targeted single-run lookup should surface the real error, not swallow
    it. The write path's strictness is unchanged; this is read-side
    tolerance for the list view only."""
    run_id = row["run_id"] if "run_id" in row.keys() else "unknown"
    try:
        return row_to_run(row)
    except (ValidationError, DurableIntegrityError, ValueError) as exc:
        logger.error("workflow_run_row_unreadable run_id=%s error=%s", run_id, exc)
        return None


def list_runs(
    connect_fn: Any, *, tenant_id: str | None, workflow_id: str | None,
    status: str | None, limit: int, cursor: str | None,
) -> tuple[list[RunRecord], str | None]:
    where, params = [], []
    for column, value in (("tenant_id", tenant_id), ("workflow_id", workflow_id), ("status", status)):
        if value is not None:
            where.append(f"{column}=?")
            params.append(value)
    if cursor:
        current = PaginationCursor.decode(cursor)
        where.append("(updated_at < ? OR (updated_at = ? AND run_id < ?))")
        params.extend([current.updated_at, current.updated_at, current.run_id])
    sql = "SELECT * FROM runs" + (" WHERE " + " AND ".join(where) if where else "")
    sql += " ORDER BY updated_at DESC,run_id DESC LIMIT ?"
    with connect_fn() as conn:
        rows = conn.execute(sql, tuple(params + [int(limit)])).fetchall()
    records = [record for record in (_row_to_run_lenient(row) for row in rows) if record is not None]
    next_cursor = None
    if len(rows) == limit:
        # Cursor advances past the last RAW row fetched, not the last
        # surviving record — an unreadable row must still be paged past,
        # never re-fetched forever on the next page (item 12c).
        last_row = rows[-1]
        next_cursor = PaginationCursor(
            updated_at=iso_format(parse_datetime(last_row["updated_at"])),
            run_id=last_row["run_id"],
        ).encode()
    return records, next_cursor
