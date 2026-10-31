from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

from factory.telemetry.runtime.retention import run_retention


def _source(path) -> None:
    with sqlite3.connect(path) as conn:
        conn.execute("""CREATE TABLE documents (
            id TEXT NOT NULL, collection TEXT NOT NULL, data TEXT NOT NULL,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
            PRIMARY KEY(collection,id))""")
        rows = [
            ("s1", "telemetry_spans", json.dumps({"otel_json": "span"}),
             "2026-08-01T00:00:00+00:00", "2026-08-01T00:00:00+00:00"),
            ("m1", "telemetry_metrics", json.dumps({"otel_json": "metric"}),
             "2026-08-01T01:00:00+00:00", "2026-08-01T01:00:00+00:00"),
            ("e1", "eval_results", json.dumps({"score": 1}),
             "2026-08-01T00:00:00+00:00", "2026-08-01T00:00:00+00:00"),
        ]
        conn.executemany("INSERT INTO documents VALUES(?,?,?,?,?)", rows)


def test_retention_rolls_up_telemetry_and_preserves_general_documents(tmp_path) -> None:
    source, target = tmp_path / "docs.db", tmp_path / "telemetry.db"
    _source(source)
    result = run_retention(
        source, target, raw_days=7, rollup_days=365,
        now=datetime(2026, 9, 11, tzinfo=timezone.utc),
    )
    assert result.rolled_up_days == 2
    assert result.source_rows_deleted == 2
    with sqlite3.connect(source) as conn:
        assert conn.execute("SELECT collection FROM documents").fetchall() == [
            ("eval_results",),
        ]
    with sqlite3.connect(target) as conn:
        rows = conn.execute(
            "SELECT collection,row_count FROM telemetry_daily_rollups ORDER BY collection"
        ).fetchall()
    assert rows == [("telemetry_metrics", 1), ("telemetry_spans", 1)]
    assert result.source_bytes_after < 1_000_000


def test_invalid_retention_bounds_fail_closed(tmp_path) -> None:
    source, target = tmp_path / "docs.db", tmp_path / "telemetry.db"
    _source(source)
    for raw_days, rollup_days in ((0, 365), (91, 365), (7, 29)):
        try:
            run_retention(source, target, raw_days=raw_days, rollup_days=rollup_days)
        except ValueError:
            pass
        else:
            raise AssertionError("invalid retention was accepted")


def test_retry_never_downgrades_rollup_after_partial_source_delete(tmp_path) -> None:
    source, target = tmp_path / "docs.db", tmp_path / "telemetry.db"
    _source(source)
    with sqlite3.connect(target) as conn:
        conn.execute("""CREATE TABLE telemetry_daily_rollups (
            day TEXT NOT NULL, collection TEXT NOT NULL, row_count INTEGER NOT NULL,
            payload_bytes INTEGER NOT NULL, PRIMARY KEY(day,collection))""")
        conn.execute(
            "INSERT INTO telemetry_daily_rollups VALUES(?,?,?,?)",
            ("2026-08-01", "telemetry_spans", 10, 999),
        )
    run_retention(source, target, compact_source=False)
    with sqlite3.connect(target) as conn:
        assert conn.execute(
            "SELECT row_count,payload_bytes FROM telemetry_daily_rollups "
            "WHERE day='2026-08-01' AND collection='telemetry_spans'"
        ).fetchone() == (10, 999)


def test_dedicated_raw_rows_are_rolled_up_before_pruning(tmp_path) -> None:
    source, target = tmp_path / "missing.db", tmp_path / "telemetry.db"
    _source(target)
    result = run_retention(
        source, target, raw_days=7, rollup_days=365,
        compact_source=False, now=datetime(2026, 9, 11, tzinfo=timezone.utc),
    )
    assert result.raw_rows_pruned == 2
    with sqlite3.connect(target) as conn:
        assert conn.execute("SELECT collection FROM documents").fetchall() == [
            ("eval_results",),
        ]
        assert conn.execute(
            "SELECT sum(row_count) FROM telemetry_daily_rollups"
        ).fetchone() == (2,)
