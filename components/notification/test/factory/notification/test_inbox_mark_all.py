"""Store-level tests for the count-fenced mark-all-read operation.

Proves the single fenced statement is all-or-nothing: a correct
``expected_unread_count`` transitions every unread row (revision+1, UTC
read_at); a drifted count mutates zero rows and raises, never partially.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from factory.notification.runtime.adapters.inbox_store_sql import SqlInboxStore
from factory.notification.runtime.inbox_models import (
    NotificationRecord, Priority, UnreadCountConflictError,
)
from factory.notification.runtime.inbox_targets import SessionTarget
from factory.storage.interface import StorageRuntime

_T = "tenant-1"
_NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


@pytest.fixture
def store(tmp_path):
    return SqlInboxStore(StorageRuntime().get_sql_store(
        "sqlite", db_path=str(tmp_path / "inbox.db")))


def _rec(nid: str, dk: str, owner: str = "owner-1") -> NotificationRecord:
    return NotificationRecord(
        tenant_id=_T, owner_id=owner, notification_id=nid, kind="schedule_fired",
        title="hi", priority=Priority.DEFAULT,
        target=SessionTarget(session_id="s"), dedupe_key=dk, created_at=_NOW)


def _seed(store, n: int, owner: str = "owner-1") -> None:
    for i in range(n):
        store.create_or_replay(_rec(f"n-{i}", f"dk-{i}", owner))


def test_matching_count_marks_all_unread(store) -> None:
    _seed(store, 3)
    marked = store.mark_all_read(_T, "owner-1", expected_unread_count=3, read_at=_NOW)
    assert marked == 3
    assert store.list(_T, "owner-1", limit=10, unread_only=True) == []
    for row in store.list(_T, "owner-1", limit=10):
        assert row.read_at is not None and row.revision == 2


def test_wrong_count_conflicts_with_zero_mutation(store) -> None:
    _seed(store, 3)
    with pytest.raises(UnreadCountConflictError):
        store.mark_all_read(_T, "owner-1", expected_unread_count=2, read_at=_NOW)
    # No partial mutation: every row is still unread at revision 1.
    unread = store.list(_T, "owner-1", limit=10, unread_only=True)
    assert len(unread) == 3
    assert all(r.read_at is None and r.revision == 1 for r in unread)


def test_expected_zero_on_empty_is_success(store) -> None:
    assert store.mark_all_read(_T, "owner-1", expected_unread_count=0,
                               read_at=_NOW) == 0


def test_expected_zero_with_unread_conflicts(store) -> None:
    _seed(store, 2)
    with pytest.raises(UnreadCountConflictError):
        store.mark_all_read(_T, "owner-1", expected_unread_count=0, read_at=_NOW)
    assert len(store.list(_T, "owner-1", limit=10, unread_only=True)) == 2


def test_owner_scoped_and_ignores_already_read(store) -> None:
    _seed(store, 2, owner="owner-1")
    _seed(store, 2, owner="owner-2")
    store.mark_read(_T, "owner-1", "n-0", expected_revision=1, read_at=_NOW)
    # owner-1 now has exactly one unread; fence on 1 marks only it.
    assert store.mark_all_read(_T, "owner-1", expected_unread_count=1,
                               read_at=_NOW) == 1
    # owner-2 untouched.
    assert len(store.list(_T, "owner-2", limit=10, unread_only=True)) == 2


def test_naive_timestamp_rejected_before_write(store) -> None:
    _seed(store, 1)
    with pytest.raises(ValueError, match="timezone-aware"):
        store.mark_all_read(_T, "owner-1", expected_unread_count=1,
                            read_at=datetime(2026, 1, 1))
    assert store.list(_T, "owner-1", limit=10, unread_only=True)[0].revision == 1
