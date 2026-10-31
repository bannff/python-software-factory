"""Deterministic SQLite telemetry retention and daily rollup."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

_COLLECTIONS = ("telemetry_spans", "telemetry_metrics", "telemetry_logs")


class RetentionResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
    rolled_up_days: int = Field(ge=0)
    source_rows_deleted: int = Field(ge=0)
    raw_rows_pruned: int = Field(ge=0)
    rollups_pruned: int = Field(ge=0)
    source_bytes_after: int = Field(ge=0)


def run_retention(
    source_path: Path, telemetry_path: Path, *, raw_days: int = 7,
    rollup_days: int = 365, compact_source: bool = True,
    now: datetime | None = None,
) -> RetentionResult:
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None or not 1 <= raw_days <= 90 or not 30 <= rollup_days <= 3650:
        raise ValueError("invalid telemetry retention policy")
    source_path, telemetry_path = source_path.resolve(), telemetry_path.resolve()
    telemetry_path.parent.mkdir(parents=True, exist_ok=True)
    rolled = _rollup_documents(source_path, telemetry_path)
    rolled += _rollup_documents(telemetry_path, telemetry_path)
    deleted = _delete_source_telemetry(source_path)
    raw_cutoff = (current - timedelta(days=raw_days)).isoformat()
    rollup_cutoff = (current - timedelta(days=rollup_days)).date().isoformat()
    with sqlite3.connect(telemetry_path) as conn:
        _init_target(conn)
        raw = conn.execute(
            "DELETE FROM documents WHERE collection IN (?,?,?) AND created_at<?",
            (*_COLLECTIONS, raw_cutoff),
        ).rowcount if _table_exists(conn, "documents") else 0
        old_rollups = conn.execute(
            "DELETE FROM telemetry_daily_rollups WHERE day<?", (rollup_cutoff,),
        ).rowcount
    if compact_source and source_path.exists():
        with sqlite3.connect(source_path) as conn:
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            conn.execute("VACUUM")
    return RetentionResult(
        rolled_up_days=rolled, source_rows_deleted=deleted,
        raw_rows_pruned=max(raw, 0), rollups_pruned=max(old_rollups, 0),
        source_bytes_after=source_path.stat().st_size if source_path.exists() else 0,
    )


def _rollup_documents(source: Path, target: Path) -> int:
    if not source.exists():
        return 0
    with sqlite3.connect(source) as src:
        if not _table_exists(src, "documents"):
            return 0
        rows = src.execute(
            "SELECT substr(created_at,1,10),collection,count(*),sum(length(data)) "
            "FROM documents WHERE collection IN (?,?,?) GROUP BY 1,2",
            _COLLECTIONS,
        ).fetchall()
    with sqlite3.connect(target) as dst:
        _init_target(dst)
        dst.executemany(
            "INSERT INTO telemetry_daily_rollups(day,collection,row_count,payload_bytes) "
            "VALUES(?,?,?,?) ON CONFLICT(day,collection) DO UPDATE SET "
            "row_count=max(row_count,excluded.row_count),"
            "payload_bytes=max(payload_bytes,excluded.payload_bytes)",
            rows,
        )
    return len(rows)


def _delete_source_telemetry(source: Path) -> int:
    if not source.exists():
        return 0
    total = 0
    with sqlite3.connect(source) as conn:
        while True:
            count = conn.execute(
                "DELETE FROM documents WHERE rowid IN (SELECT rowid FROM documents "
                "WHERE collection IN (?,?,?) LIMIT 50000)", _COLLECTIONS,
            ).rowcount
            total += max(count, 0)
            conn.commit()
            if count < 50000:
                break
    return total


def _init_target(conn: sqlite3.Connection) -> None:
    conn.execute("""CREATE TABLE IF NOT EXISTS telemetry_daily_rollups (
        day TEXT NOT NULL, collection TEXT NOT NULL, row_count INTEGER NOT NULL,
        payload_bytes INTEGER NOT NULL, PRIMARY KEY(day,collection))""")


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,),
    ).fetchone() is not None


__all__ = ["RetentionResult", "run_retention"]
