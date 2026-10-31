"""SQLite-backed event history store for replay and audit."""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from .models import EventHistoryEntry


class SQLiteEventHistoryStore:
    """SQLite-backed event history store for replay and audit."""

    def __init__(self, db_path: str | None = None) -> None:
        self.db_path = db_path or os.environ.get("EVENTS_HISTORY_SQLITE_PATH") or os.environ.get(
            "EVENTS_SQLITE_PATH", "./events.db"
        )
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute(
                """CREATE TABLE IF NOT EXISTS event_history (
                event_id TEXT PRIMARY KEY,
                event_type TEXT NOT NULL,
                payload TEXT,
                source TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                tenant_id TEXT,
                principal_id TEXT,
                correlation_id TEXT,
                metadata TEXT
            )"""
            )
            for col in ("timestamp", "event_type", "source", "tenant_id"):
                conn.execute(
                    f"CREATE INDEX IF NOT EXISTS idx_history_{col} ON event_history({col})"
                )
            conn.commit()

    def record(self, entry: EventHistoryEntry) -> None:
        """Record an event in history."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO event_history VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    entry.event_id,
                    entry.event_type,
                    json.dumps(entry.payload),
                    entry.source,
                    entry.timestamp.isoformat(),
                    entry.tenant_id,
                    entry.principal_id,
                    entry.correlation_id,
                    json.dumps(entry.metadata),
                ),
            )
            conn.commit()

    def get(self, event_id: str) -> EventHistoryEntry | None:
        """Get a history entry by event ID."""
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT * FROM event_history WHERE event_id=?", (event_id,)
            ).fetchone()
        return _row_to_history_entry(row) if row else None

    def list_entries(
        self,
        event_type: str | None = None,
        source: str | None = None,
        tenant_id: str | None = None,
        limit: int = 100,
    ) -> list[EventHistoryEntry]:
        """List history entries with optional filters."""
        sql, params = "SELECT * FROM event_history WHERE 1=1", []
        if event_type:
            sql += " AND event_type=?"
            params.append(event_type)
        if source:
            sql += " AND source=?"
            params.append(source)
        if tenant_id:
            sql += " AND tenant_id=?"
            params.append(tenant_id)
        sql += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(sql, params).fetchall()
        return [_row_to_history_entry(row) for row in rows]

    def prune(self, before: datetime) -> int:
        """Remove history entries older than the cutoff timestamp."""
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute(
                "DELETE FROM event_history WHERE timestamp < ?",
                (before.isoformat(),),
            )
            conn.commit()
            return cur.rowcount

    def count(self) -> int:
        """Count total entries in history."""
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute("SELECT COUNT(*) FROM event_history").fetchone()
        return row[0] if row else 0


def _row_to_history_entry(row: tuple[Any, ...]) -> EventHistoryEntry:
    """Convert a sqlite row into an EventHistoryEntry."""
    return EventHistoryEntry(
        event_id=row[0],
        event_type=row[1],
        payload=json.loads(row[2]) if row[2] else {},
        source=row[3],
        timestamp=datetime.fromisoformat(row[4]),
        tenant_id=row[5],
        principal_id=row[6],
        correlation_id=row[7],
        metadata=json.loads(row[8]) if row[8] else {},
    )
