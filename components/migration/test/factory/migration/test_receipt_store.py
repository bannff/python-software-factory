"""Unit tests for the SQL-backed durable migration receipt store.

Covers commit/replay/conflict, FAILED-supersede, owner isolation, plan
binding, resume-cursor CAS, outcome counts, and restart continuity — all
through ``factory.storage.interface`` public SQL.
"""
from __future__ import annotations

import pytest

from factory.migration.runtime.adapters.receipt_store_sql import SqlReceiptStore
from factory.migration.runtime.receipt_models import (
    CommitStatus, CursorConflictError, ImportOutcome, ImportReceipt, PageCursor,
    PlanIdentity,
)
from factory.storage.interface import StorageRuntime

_T = "tenant-1"
_A = "kirocrew-v1"
_FP = "sha256:" + "f" * 32
_D1 = "sha256:" + "1" * 32
_D2 = "sha256:" + "2" * 32


@pytest.fixture
def store(tmp_path):
    yield SqlReceiptStore(StorageRuntime().get_sql_store(
        "sqlite", db_path=str(tmp_path / "m.db")))


def _r(owner="owner-1", kind="memory", rid="rec-1", digest=_D1,
       outcome=ImportOutcome.IMPORTED) -> ImportReceipt:
    return ImportReceipt(tenant_id=_T, owner_id=owner, adapter=_A,
                         source_fingerprint=_FP, kind=kind, source_record_id=rid,
                         target_digest=digest, outcome=outcome)


def test_first_commit_then_find(store) -> None:
    assert store.record_receipt(_r()).status is CommitStatus.COMMITTED
    found = store.find_receipt(_T, "owner-1", _A, _FP, "memory", "rec-1")
    assert found is not None and found.target_digest == _D1


def test_exact_replay_skips(store) -> None:
    store.record_receipt(_r())
    again = store.record_receipt(_r())
    assert again.status is CommitStatus.REPLAYED
    assert again.receipt.revision == 1


def test_changed_material_conflicts_without_overwrite(store) -> None:
    store.record_receipt(_r(digest=_D1))
    conflict = store.record_receipt(_r(digest=_D2))
    assert conflict.status is CommitStatus.CONFLICT
    assert store.find_receipt(_T, "owner-1", _A, _FP, "memory", "rec-1").target_digest == _D1


def test_failed_receipt_is_superseded_on_retry(store) -> None:
    store.record_receipt(_r(outcome=ImportOutcome.FAILED, digest=_D1))
    retried = store.record_receipt(_r(outcome=ImportOutcome.IMPORTED, digest=_D2))
    assert retried.status is CommitStatus.SUPERSEDED
    latest = store.find_receipt(_T, "owner-1", _A, _FP, "memory", "rec-1")
    assert latest.outcome is ImportOutcome.IMPORTED
    assert latest.target_digest == _D2 and latest.revision == 2


def test_owner_isolation(store) -> None:
    store.record_receipt(_r(owner="owner-1"))
    assert store.find_receipt(_T, "owner-2", _A, _FP, "memory", "rec-1") is None
    # same identity under a different owner is an independent row
    assert store.record_receipt(_r(owner="owner-2")).status is CommitStatus.COMMITTED
    assert len(store.list_receipts(_T, "owner-1", _A, _FP)) == 1
    assert len(store.list_receipts(_T, "owner-2", _A, _FP)) == 1


def test_list_and_counts(store) -> None:
    store.record_receipt(_r(rid="rec-1", outcome=ImportOutcome.IMPORTED))
    store.record_receipt(_r(rid="rec-2", kind="lessons", outcome=ImportOutcome.SKIPPED))
    store.record_receipt(_r(rid="rec-3", outcome=ImportOutcome.FAILED))
    assert len(store.list_receipts(_T, "owner-1", _A, _FP)) == 3
    assert len(store.list_receipts(_T, "owner-1", _A, _FP, kind="lessons")) == 1
    counts = store.outcome_counts(_T, "owner-1", _A, _FP)
    assert counts == {"imported": 1, "skipped": 1, "failed": 1}


def test_bind_plan_commit_replay_conflict(store) -> None:
    plan = PlanIdentity(tenant_id=_T, owner_id="owner-1", adapter=_A,
                        source_fingerprint=_FP, plan_digest=_D1, kinds=("memory",))
    assert store.bind_plan(plan).status is CommitStatus.COMMITTED
    assert store.bind_plan(plan).status is CommitStatus.REPLAYED
    changed = plan.model_copy(update={"plan_digest": _D2, "kinds": ("lessons",)})
    assert store.bind_plan(changed).status is CommitStatus.COMMITTED
    assert store.get_plan(_T, "owner-1", _A, _FP, _D1) == plan
    assert store.get_plan(_T, "owner-1", _A, _FP, _D2) == changed
    collision = plan.model_copy(update={"kinds": ("lessons",)})
    assert store.bind_plan(collision).status is CommitStatus.CONFLICT


def _cur(owner="owner-1", kind="memory", page=0, plan=_D1) -> PageCursor:
    return PageCursor(tenant_id=_T, owner_id=owner, adapter=_A,
                      source_fingerprint=_FP, plan_digest=plan,
                      kind=kind, page_index=page)


def test_cursor_cas_lifecycle(store) -> None:
    created = store.save_cursor(_cur(page=0))
    assert created.revision == 1
    with pytest.raises(CursorConflictError):
        store.save_cursor(_cur(page=1))  # create when it already exists
    advanced = store.save_cursor(_cur(page=5), expected_revision=1)
    assert advanced.revision == 2 and advanced.page_index == 5
    with pytest.raises(CursorConflictError):
        store.save_cursor(_cur(page=9), expected_revision=1)  # stale fence
    assert store.load_cursor(_T, "owner-1", _A, _FP, _D1, "memory").page_index == 5
    assert store.load_cursor(_T, "owner-2", _A, _FP, _D1, "memory") is None  # owner-scoped
    assert store.load_cursor(_T, "owner-1", _A, _FP, _D2, "memory") is None  # plan-scoped


def test_restart_continuity(tmp_path) -> None:
    db = str(tmp_path / "restart.db")
    s1 = SqlReceiptStore(StorageRuntime().get_sql_store("sqlite", db_path=db))
    s1.record_receipt(_r(digest=_D1))
    s1.save_cursor(_cur(page=3))
    s2 = SqlReceiptStore(StorageRuntime().get_sql_store("sqlite", db_path=db))
    assert s2.find_receipt(_T, "owner-1", _A, _FP, "memory", "rec-1").target_digest == _D1
    assert s2.load_cursor(_T, "owner-1", _A, _FP, _D1, "memory").page_index == 3
    # replay after restart still skips
    assert s2.record_receipt(_r(digest=_D1)).status is CommitStatus.REPLAYED
