"""Fail-closed migration tests for retired managed graph evidence."""
from __future__ import annotations

import hashlib
import sqlite3
import threading

import pytest
from factory.workflow.runtime.canonical import canonical_json

from .execution_engine_support import BlockingInvoker, enroll, runtime


def _active_attempt(tmp_path):
    invoker = BlockingInvoker()
    owner = runtime(tmp_path, invoker)
    result: dict = {}
    errors: list[BaseException] = []
    thread = threading.Thread(
        target=lambda: _enroll(owner, result, errors), daemon=True,
    )
    thread.start()
    assert invoker.started.wait(timeout=5)
    record = owner.durable_storage.get_run_by_key(run_key="projection")
    assert record is not None
    attempt = owner.durable_storage.list_task_attempts(run_id=record.run_id)[0]
    return owner, invoker, thread, errors, record.run_id, attempt


def _enroll(owner, result, errors) -> None:
    try:
        result.update(enroll(owner, "strands_graph", key="projection"))
    except BaseException as exc:
        errors.append(exc)


def _insert_legacy(database, attempt, run_id, *, raw_digest: str, raw_json: str) -> None:
    with sqlite3.connect(database) as conn:
        conn.execute(
            "INSERT INTO managed_graph_events VALUES(?,?,?,?,?,?,?,?,?)",
            (attempt["attempt_id"], attempt["revision"], 0, run_id, "m" * 64,
             raw_digest, False, raw_json, "2026-01-01T00:00:00+00:00"),
        )


def _release(invoker, thread, errors) -> None:
    invoker.release.set()
    thread.join(timeout=5)
    assert not thread.is_alive() and not errors


def test_legacy_projection_rejects_malformed_raw_digest_atomically(tmp_path) -> None:
    owner, invoker, thread, errors, run_id, attempt = _active_attempt(tmp_path)
    database = tmp_path / "config" / "state.db"
    raw_json = canonical_json({"event": "legacy"})
    _insert_legacy(database, attempt, run_id, raw_digest="0" * 64, raw_json=raw_json)
    try:
        with pytest.raises(ValueError, match="legacy event raw_digest mismatch"):
            owner.durable_storage.init_schema()
        with sqlite3.connect(database) as conn:
            assert conn.execute("SELECT COUNT(*) FROM execution_events").fetchone()[0] == 0
    finally:
        _release(invoker, thread, errors)


def test_legacy_projection_rejects_conflicting_generic_row(tmp_path) -> None:
    owner, invoker, thread, errors, run_id, attempt = _active_attempt(tmp_path)
    database = tmp_path / "config" / "state.db"
    raw_json = canonical_json({"event": "legacy"})
    raw_digest = hashlib.sha256(raw_json.encode()).hexdigest()
    _insert_legacy(database, attempt, run_id, raw_digest=raw_digest, raw_json=raw_json)
    with sqlite3.connect(database) as conn:
        conn.execute(
            "INSERT INTO execution_events VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (attempt["attempt_id"], attempt["revision"], 0, run_id, "wrong-engine",
             "m" * 64, "m" * 64, "m" * 64, raw_digest, False, raw_json, "{}",
             "2026-01-01T00:00:00+00:00"),
        )
    try:
        with pytest.raises(ValueError, match="legacy event projection conflict"):
            owner.durable_storage.init_schema()
    finally:
        _release(invoker, thread, errors)
