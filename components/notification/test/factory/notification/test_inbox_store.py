"""Unit tests for the SQL-backed durable notification inbox store.

Covers create/replay/conflict, opaque owner isolation, newest-first list with
unread filter and paging, revision-CAS mark read/unread, stale/foreign CAS,
and restart continuity — all through ``factory.storage.interface`` public SQL.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from factory.notification.runtime.adapters.inbox_store_sql import SqlInboxStore
from factory.notification.runtime.inbox_models import (
    InboxCommitStatus, NotificationNotFoundError, NotificationRecord, Priority,
    RevisionConflictError,
)
from factory.notification.runtime.inbox_targets import SessionTarget
from factory.storage.interface import StorageRuntime

_T = "tenant-1"
_NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


@pytest.fixture
def store(tmp_path):
    return SqlInboxStore(StorageRuntime().get_sql_store(
        "sqlite", db_path=str(tmp_path / "inbox.db")))


def _rec(owner="owner-1", nid="ntf-1", dk="dk-1", title="hello", body="",
         created=_NOW, priority=Priority.DEFAULT) -> NotificationRecord:
    return NotificationRecord(
        tenant_id=_T, owner_id=owner, notification_id=nid, kind="schedule_fired",
        title=title, body=body, priority=priority,
        target=SessionTarget(session_id="sess-1"), dedupe_key=dk, created_at=created)


def test_create_then_get(store) -> None:
    assert store.create_or_replay(_rec()).status is InboxCommitStatus.CREATED
    got = store.get(_T, "owner-1", "ntf-1")
    assert got is not None and got.title == "hello" and got.revision == 1


def test_exact_replay_is_noop(store) -> None:
    store.create_or_replay(_rec())
    again = store.create_or_replay(_rec(nid="ntf-2"))  # same dedupe key, same content
    assert again.status is InboxCommitStatus.REPLAYED
    assert again.record.notification_id == "ntf-1"  # first row wins
    assert store.get(_T, "owner-1", "ntf-2") is None


def test_conflict_without_overwrite(store) -> None:
    store.create_or_replay(_rec(title="original"))
    conflict = store.create_or_replay(_rec(nid="ntf-9", title="changed"))
    assert conflict.status is InboxCommitStatus.CONFLICT
    assert store.get(_T, "owner-1", "ntf-1").title == "original"


def test_owner_isolation_is_opaque(store) -> None:
    store.create_or_replay(_rec(owner="owner-1"))
    assert store.get(_T, "owner-2", "ntf-1") is None
    # same dedupe key under a different owner is independent
    assert store.create_or_replay(
        _rec(owner="owner-2")).status is InboxCommitStatus.CREATED
    assert len(store.list(_T, "owner-1", limit=10)) == 1
    assert len(store.list(_T, "owner-2", limit=10)) == 1


def test_list_newest_first_unread_and_paging(store) -> None:
    for i in range(3):
        store.create_or_replay(_rec(nid=f"ntf-{i}", dk=f"dk-{i}",
                                    created=_NOW + timedelta(minutes=i)))
    rows = store.list(_T, "owner-1", limit=10)
    assert [r.notification_id for r in rows] == ["ntf-2", "ntf-1", "ntf-0"]
    page = store.list(_T, "owner-1", limit=1, offset=1)
    assert [r.notification_id for r in page] == ["ntf-1"]
    store.mark_read(_T, "owner-1", "ntf-2", expected_revision=1, read_at=_NOW)
    unread = store.list(_T, "owner-1", limit=10, unread_only=True)
    assert [r.notification_id for r in unread] == ["ntf-1", "ntf-0"]


def test_mark_read_then_unread_cas(store) -> None:
    store.create_or_replay(_rec())
    read = store.mark_read(_T, "owner-1", "ntf-1", expected_revision=1, read_at=_NOW)
    assert read.read_at is not None and read.revision == 2
    back = store.mark_unread(_T, "owner-1", "ntf-1", expected_revision=2)
    assert back.read_at is None and back.revision == 3


def test_stale_revision_raises(store) -> None:
    store.create_or_replay(_rec())
    store.mark_read(_T, "owner-1", "ntf-1", expected_revision=1, read_at=_NOW)
    with pytest.raises(RevisionConflictError):
        store.mark_read(_T, "owner-1", "ntf-1", expected_revision=1, read_at=_NOW)


def test_foreign_mark_is_opaque_not_found(store) -> None:
    store.create_or_replay(_rec(owner="owner-1"))
    with pytest.raises(NotificationNotFoundError):
        store.mark_read(_T, "owner-2", "ntf-1", expected_revision=1, read_at=_NOW)
    with pytest.raises(NotificationNotFoundError):
        store.mark_read(_T, "owner-1", "absent", expected_revision=1, read_at=_NOW)


def test_naive_read_timestamp_is_rejected_before_write(store) -> None:
    store.create_or_replay(_rec())
    with pytest.raises(ValueError, match="timezone-aware"):
        store.mark_read(
            _T, "owner-1", "ntf-1", expected_revision=1,
            read_at=datetime(2026, 1, 1),
        )
    assert store.get(_T, "owner-1", "ntf-1").revision == 1


def test_bad_page_bounds_rejected(store) -> None:
    with pytest.raises(ValueError):
        store.list(_T, "owner-1", limit=0)
    with pytest.raises(ValueError):
        store.list(_T, "owner-1", limit=10, offset=-1)


def test_restart_continuity(tmp_path) -> None:
    db = str(tmp_path / "restart.db")
    s1 = SqlInboxStore(StorageRuntime().get_sql_store("sqlite", db_path=db))
    s1.create_or_replay(_rec())
    s1.mark_read(_T, "owner-1", "ntf-1", expected_revision=1, read_at=_NOW)
    s2 = SqlInboxStore(StorageRuntime().get_sql_store("sqlite", db_path=db))
    got = s2.get(_T, "owner-1", "ntf-1")
    assert got is not None and got.revision == 2 and got.read_at is not None
    assert s2.create_or_replay(_rec()).status is InboxCommitStatus.REPLAYED
