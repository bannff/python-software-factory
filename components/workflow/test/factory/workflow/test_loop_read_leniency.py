"""Item 12(b)/(c) (owner smoke #2, P1 BLOCK #2): the read path must never
reject a row the write path once produced. A loop record written before
today's stricter ``LoopRecord`` invariants existed (e.g. the
``next_cycle == last_settled_cycle + 1`` contiguity check, added after some
loops were already interrupted mid-cycle by the M7.6 dogfood-loop
gateway-restart incident) fails ``model_validate_json`` on every read,
crashing ``workflow.list_loops`` for every caller — not just the one bad
row. Reproduces with a raw SQL insert bypassing the strict model (exactly
how an old writer, or a hand-repaired row, would have landed one), then
proves ``list_loops`` recovers past it instead of raising.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone

from factory.workflow.runtime.storage.sqlite import SqliteWorkflowStorage


def _valid_loop_json(loop_id: str, **overrides) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    base = {
        "tenant_id": "tenant", "owner_id": "owner", "loop_id": loop_id,
        "origin_session_id": "session", "origin_thread_id": "thread",
        "agent_id": "developer", "kind": "goal",
        "objective": "advance work", "cycle_instructions": "read, act, verify",
        "interval_seconds": 60, "max_cycles": 24, "runtime_deadline": None,
        "project_root": "/tmp/proj",
        "project_root_digest": hashlib.sha256(b"/tmp/proj").hexdigest(),
        "state": "active", "terminal_reason": None,
        "next_cycle": 2, "last_settled_cycle": 1,
        "blocker_digest": None, "blocker_projected": False,
        "revision": 3, "created_at": now, "updated_at": now,
        "initiation_envelope": {
            "tenant_id": "tenant", "principal_id": "owner", "session_id": "thread",
            "timestamp": now, "attributes": {},
        },
    }
    base.update(overrides)
    return base


def _insert_raw_row(db_path, loop_id: str, raw: dict) -> None:
    """Bypass LoopRecord entirely — an old writer or a hand-migrated row
    would land exactly like this: whatever the schema accepted at the time,
    not necessarily what today's stricter model would accept."""
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "INSERT INTO workflow_loops VALUES(?,?,?,?,?,?,?)",
            ("tenant", "owner", loop_id, raw["state"], raw["revision"],
             raw["updated_at"], json.dumps(raw)),
        )
        conn.commit()
    finally:
        conn.close()


def test_list_loops_recovers_past_a_pre_contiguity_invariant_row(tmp_path) -> None:
    storage = SqliteWorkflowStorage(tmp_path / "workflow.db")
    storage.init_schema()
    # A loop interrupted mid-settlement before the contiguity invariant
    # existed: next_cycle=5 but last_settled_cycle=1 (a gap), which today's
    # LoopRecord._sequence model_validator rejects outright.
    _insert_raw_row(tmp_path / "workflow.db", "old_loop_1", _valid_loop_json(
        "old_loop_1", next_cycle=5, last_settled_cycle=1,
    ))
    _insert_raw_row(tmp_path / "workflow.db", "good_loop_1", _valid_loop_json("good_loop_1"))

    # Must not raise, and must not silently drop the good row alongside it.
    loops = storage.list_loops("tenant", "owner", limit=10)
    assert [loop.loop_id for loop in loops] == ["good_loop_1"]


def test_list_loops_recovers_past_a_naive_timestamp_row(tmp_path) -> None:
    storage = SqliteWorkflowStorage(tmp_path / "workflow.db")
    storage.init_schema()
    # A loop written before the tz-aware timestamp validator existed.
    bad = _valid_loop_json("naive_loop_1")
    bad["created_at"] = "2026-01-01T00:00:00"  # no tzinfo
    _insert_raw_row(tmp_path / "workflow.db", "naive_loop_1", bad)
    _insert_raw_row(tmp_path / "workflow.db", "good_loop_2", _valid_loop_json("good_loop_2"))

    loops = storage.list_loops("tenant", "owner", limit=10)
    assert [loop.loop_id for loop in loops] == ["good_loop_2"]


def test_get_loop_returns_none_for_an_unreadable_row_not_a_crash(tmp_path) -> None:
    storage = SqliteWorkflowStorage(tmp_path / "workflow.db")
    storage.init_schema()
    _insert_raw_row(tmp_path / "workflow.db", "old_loop_2", _valid_loop_json(
        "old_loop_2", next_cycle=9, last_settled_cycle=1,
    ))
    # A caller asking for THIS specific loop by id gets an honest "not
    # found" (the record is unreadable, distinct from never having
    # existed, but neither should crash the caller) rather than a 500.
    assert storage.get_loop("tenant", "owner", "old_loop_2") is None
