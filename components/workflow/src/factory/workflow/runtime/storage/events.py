"""Event storage operations for workflow sqlite backend."""

from __future__ import annotations

import json
import sqlite3

from factory.mcp_utils.interface import (
    is_protected_payload, protected_error_value, validate_protected_persistence,
)
from factory.workflow.runtime.canonical import canonical_json
from datetime import datetime
from typing import Any

from factory.workflow.runtime.envelope import Envelope
from factory.workflow.runtime.models import EventRecord
from .models import iso_format, parse_datetime


def row_to_event(row: sqlite3.Row) -> EventRecord:
    """Convert a database row to an EventRecord."""
    return EventRecord(
        id=int(row["id"]),
        run_id=row["run_id"],
        event_type=row["event_type"],
        payload=json.loads(row["payload_json"]),
        created_at=parse_datetime(row["created_at"]),
    )


def append_event(
    connect_fn: Any,
    *,
    run_id: str,
    event_type: str,
    payload: dict[str, Any],
    envelope: Envelope,
    now: datetime,
) -> EventRecord:
    """Append an event to a workflow run."""
    protected = is_protected_payload(payload)
    if protected:
        validate_protected_persistence(payload, protected=True)
    payload = protected_error_value(payload, protected=protected)
    validate_protected_persistence(payload, protected=protected)
    with connect_fn() as conn:
        cur = conn.execute(
            """
            INSERT INTO events(run_id, event_type, payload_json, created_at, envelope_json)
            VALUES(?, ?, ?, ?, ?)
            """,
            (
                run_id,
                event_type,
                canonical_json(payload),
                iso_format(now),
                envelope.model_dump_json(),
            ),
        )
        event_id = int(cur.lastrowid)

    with connect_fn() as conn:
        row = conn.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
        if row is None:
            raise RuntimeError("failed to fetch inserted event")
        return row_to_event(row)


def get_events_since(
    connect_fn: Any,
    *,
    run_id: str,
    after_event_id: int,
) -> list[EventRecord]:
    """Get events for a run after a specific event ID."""
    with connect_fn() as conn:
        rows = conn.execute(
            "SELECT * FROM events WHERE run_id = ? AND id > ? ORDER BY id ASC",
            (run_id, int(after_event_id)),
        ).fetchall()
        return [row_to_event(r) for r in rows]


def get_last_event_id(connect_fn: Any, *, run_id: str) -> int:
    """Get the last event ID for a run."""
    with connect_fn() as conn:
        row = conn.execute(
            "SELECT COALESCE(MAX(id), 0) AS max_id FROM events WHERE run_id = ?",
            (run_id,),
        ).fetchone()
        if row is None:
            return 0
        return int(row["max_id"])
