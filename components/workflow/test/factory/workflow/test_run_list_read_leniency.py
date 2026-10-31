"""Item 12(b)/(c) (owner smoke #2, P1 BLOCK #2): ``workflow.list_runs`` must
never let one unreadable run row crash the whole caller. Reproduces with a
raw SQL insert bypassing ``create_run`` entirely (exactly how a row written
before ``run_binding.py``'s durable-identity check existed would look:
``workflow_version_id`` set on a row whose ``run_id`` no longer matches the
canonical recomputation), then proves ``list_runs`` recovers past it while
still returning every other, valid run — and that pagination advances past
the bad row instead of re-fetching it forever.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

from factory.workflow.runtime.envelope import Envelope
from factory.workflow.runtime.storage.sqlite import SqliteWorkflowStorage


def _insert_raw_run(db_path, *, run_id: str, updated_at: str, workflow_version_id: str | None = None) -> None:
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "INSERT INTO runs(run_id,tenant_id,workflow_id,workflow_version,status,"
            "current_step_id,waiting_for_event_type,last_event_id,started_at,updated_at,"
            "input_json,result_json,error,envelope_json,workflow_version_id,run_execution_id) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (run_id, None, "wf1", 1, "running", None, None, 0, updated_at, updated_at,
             json.dumps({"k": "v"}), None, None, Envelope().model_dump_json(),
             workflow_version_id, None),
        )
        conn.commit()
    finally:
        conn.close()


def _storage(tmp_path) -> SqliteWorkflowStorage:
    storage = SqliteWorkflowStorage(tmp_path / "workflow.db")
    storage.init_schema()
    return storage


def test_list_runs_recovers_past_a_durable_binding_mismatch_row(tmp_path) -> None:
    storage = _storage(tmp_path)
    now = datetime.now(timezone.utc).isoformat()
    # workflow_version_id set but run_id was never derived from it (an old
    # row from before the durable-binding check existed) -> today's
    # verify_durable_run_binding rejects it on every read.
    _insert_raw_run(tmp_path / "workflow.db", run_id="old_run_1", updated_at=now,
                     workflow_version_id="v1")
    storage.create_run(
        run_id="good_run_1", workflow_id="wf1", workflow_version=1,
        tenant_id=None, input={}, envelope=Envelope(), now=datetime.now(timezone.utc),
    )

    records, _ = storage.list_runs(
        tenant_id=None, workflow_id=None, status=None, limit=10, cursor=None,
    )
    assert [r.run_id for r in records] == ["good_run_1"]


def test_list_runs_pagination_advances_past_an_unreadable_row(tmp_path) -> None:
    storage = _storage(tmp_path)
    # Two raw rows sharing a controlled updated_at ordering, the newer one
    # unreadable. limit=1 forces exactly the unreadable row into the page.
    _insert_raw_run(tmp_path / "workflow.db", run_id="old_run_2",
                     updated_at="2026-01-02T00:00:00+00:00", workflow_version_id="v1")
    _insert_raw_run(tmp_path / "workflow.db", run_id="old_run_3",
                     updated_at="2026-01-01T00:00:00+00:00")

    records, cursor = storage.list_runs(
        tenant_id=None, workflow_id=None, status=None, limit=1, cursor=None,
    )
    # The page returned zero USABLE records (the one raw row was bad), but
    # a cursor must still exist so the next page moves past it rather than
    # looping on the same unreadable row forever.
    assert records == []
    assert cursor is not None

    records2, _ = storage.list_runs(
        tenant_id=None, workflow_id=None, status=None, limit=10, cursor=cursor,
    )
    assert [r.run_id for r in records2] == ["old_run_3"]
