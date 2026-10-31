"""SQLite event store — shared file-based persistence.

Both the API process and the Kiro MCP power process write to the same
SQLite file. WAL mode handles concurrent access. Truncated on startup
so events are session-scoped (ephemeral across restarts, durable within).
"""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path

from ..models import Event, EventFilter, EventQueryResult

_DEFAULT_PATH = "./events.db"
_COLS = "id, timestamp, source, type, payload, trace_id, session_id, principal_id"
_CREATE = f"""CREATE TABLE IF NOT EXISTS events (
    id TEXT PRIMARY KEY, timestamp TEXT NOT NULL, source TEXT NOT NULL,
    type TEXT NOT NULL, payload TEXT, trace_id TEXT,
    session_id TEXT, principal_id TEXT)"""
_INSERT = "INSERT OR REPLACE INTO events VALUES (?,?,?,?,?,?,?,?)"


def _row_to_event(row: tuple) -> Event:
    return Event(
        id=row[0], timestamp=datetime.fromisoformat(row[1]),
        source=row[2], type=row[3],
        payload=json.loads(row[4]) if row[4] else {},
        trace_id=row[5], session_id=row[6], principal_id=row[7],
    )


def _event_tuple(e: Event) -> tuple:
    return (e.id, e.timestamp.isoformat(), e.source, e.type,
            json.dumps(e.payload), e.trace_id, e.session_id, e.principal_id)


class SQLiteEventStore:
    """SQLite-backed event store for shared, session-scoped persistence."""

    def __init__(self, db_path: str | None = None):
        self.db_path = db_path or os.environ.get("EVENTS_SQLITE_PATH", _DEFAULT_PATH)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute(_CREATE)
            for col in ("timestamp", "type", "source"):
                conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{col} ON events({col})")
            conn.execute("DELETE FROM events")  # session-scoped: fresh on startup
            conn.commit()

    async def initialize(self) -> None:
        pass  # table created in __init__

    # -- Sync (used by EventsRuntime.publish) --

    def store(self, event: Event) -> str:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(_INSERT, _event_tuple(event))
            conn.commit()
        return event.id

    def get(self, event_id: str) -> Event | None:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute("SELECT * FROM events WHERE id=?", (event_id,)).fetchone()
        return _row_to_event(row) if row else None

    def list_events(self, event_type: str | None = None, source: str | None = None,
                    limit: int = 100, offset: int = 0, descending: bool = True) -> list[Event]:
        sql, params = "SELECT * FROM events WHERE 1=1", []
        if event_type:
            sql += " AND type=?"
            params.append(event_type)
        if source:
            sql += " AND source=?"
            params.append(source)
        sql += f" ORDER BY timestamp {'DESC' if descending else 'ASC'} LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        with sqlite3.connect(self.db_path) as conn:
            return [_row_to_event(r) for r in conn.execute(sql, params).fetchall()]

    # -- Async (delegate to sync — SQLite is fast enough) --

    async def emit(self, event: Event) -> str:
        return self.store(event)

    async def query(self, filter: EventFilter) -> EventQueryResult:
        sql, params = "SELECT * FROM events WHERE 1=1", []
        if filter.source:
            sql += " AND source=?"
            params.append(filter.source)
        if filter.type:
            sql += " AND type=?"
            params.append(filter.type)
        elif filter.type_prefix:
            sql += " AND type LIKE ?"
            params.append(f"{filter.type_prefix}%")
        if filter.start_time:
            sql += " AND timestamp>=?"
            params.append(filter.start_time.isoformat())
        if filter.end_time:
            sql += " AND timestamp<=?"
            params.append(filter.end_time.isoformat())
        if filter.trace_id:
            sql += " AND trace_id=?"
            params.append(filter.trace_id)
        if filter.session_id:
            sql += " AND session_id=?"
            params.append(filter.session_id)
        sql += f" ORDER BY timestamp {'DESC' if filter.descending else 'ASC'}"
        sql += " LIMIT ? OFFSET ?"
        params.extend([filter.limit, filter.offset])
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(sql, params).fetchall()
        return EventQueryResult(events=[_row_to_event(r) for r in rows])

    async def prune(self, before: datetime) -> int:
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute("DELETE FROM events WHERE timestamp<?", (before.isoformat(),))
            conn.commit()
            return cur.rowcount

    async def count(self) -> int:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute("SELECT COUNT(*) FROM events").fetchone()
            return row[0] if row else 0
