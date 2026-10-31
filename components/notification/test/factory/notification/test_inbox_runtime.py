"""Runtime-level tests: inbox injection, isolation, delegates, restart.

Direct construction with a temp config dir must yield an isolated durable DB
(no shared state across runtimes); the server ``get_runtime`` honors
``NOTIFICATION_INBOX_DB_PATH`` defaulting to ``./.storage/notification.db``.
The delivery store is never touched by inbox wiring.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from factory.notification.runtime.dispatcher import NotificationRuntime
from factory.notification.runtime.delivery import InMemoryDeliveryStore
from factory.notification.runtime.inbox_models import (
    NotificationNotFoundError, NotificationRecord, Priority, RevisionConflictError,
)
from factory.notification.runtime.inbox_targets import SessionTarget

_T = "tenant-1"
_NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _rec(nid: str = "n-1", dk: str = "dk-1", owner: str = "owner-1") -> NotificationRecord:
    return NotificationRecord(
        tenant_id=_T, owner_id=owner, notification_id=nid, kind="schedule_fired",
        title="hello", priority=Priority.DEFAULT,
        target=SessionTarget(session_id="s"), dedupe_key=dk, created_at=_NOW)


def test_delivery_store_preserved_and_inbox_added(tmp_path) -> None:
    runtime = NotificationRuntime(tmp_path)
    assert isinstance(runtime.delivery_store, InMemoryDeliveryStore)
    assert runtime.inbox_store is not None


def test_default_config_dir_is_isolated_durable_db(tmp_path) -> None:
    a = NotificationRuntime(tmp_path / "a")
    b = NotificationRuntime(tmp_path / "b")
    a.inbox_store.create_or_replay(_rec())
    # A durable file exists under A's config dir, and B never sees A's row.
    assert (tmp_path / "a" / "notification-inbox.db").exists()
    assert a.inbox_get(_T, "owner-1", "n-1").title == "hello"
    assert b.inbox_list(_T, "owner-1", limit=10) == []


def test_server_get_runtime_honors_env_db_path(tmp_path, monkeypatch) -> None:
    from factory.notification import server

    db = str(tmp_path / "env-inbox.db")
    monkeypatch.setenv("NOTIFICATION_INBOX_DB_PATH", db)
    monkeypatch.setenv("NOTIFICATION_CONFIG_DIR", str(tmp_path / "cfg"))
    runtime = server.get_runtime()
    runtime.inbox_store.create_or_replay(_rec())
    assert (tmp_path / "env-inbox.db").exists()


def test_delegates_list_get_mark_and_mark_all(tmp_path) -> None:
    runtime = NotificationRuntime(tmp_path)
    for i in range(2):
        runtime.inbox_store.create_or_replay(_rec(f"n-{i}", f"dk-{i}"))
    listed = runtime.inbox_list(_T, "owner-1", limit=10)
    assert {r.notification_id for r in listed} == {"n-0", "n-1"}
    marked = runtime.inbox_mark_read(_T, "owner-1", "n-0", expected_revision=1)
    assert marked.read_at is not None and marked.revision == 2
    assert runtime.inbox_mark_all_read(_T, "owner-1", expected_unread_count=1) == 1


def test_delegate_get_foreign_is_opaque_not_found(tmp_path) -> None:
    runtime = NotificationRuntime(tmp_path)
    runtime.inbox_store.create_or_replay(_rec(owner="owner-1"))
    with pytest.raises(NotificationNotFoundError):
        runtime.inbox_get(_T, "owner-2", "n-1")


def test_delegate_stale_revision_raises(tmp_path) -> None:
    runtime = NotificationRuntime(tmp_path)
    runtime.inbox_store.create_or_replay(_rec())
    runtime.inbox_mark_read(_T, "owner-1", "n-1", expected_revision=1)
    with pytest.raises(RevisionConflictError):
        runtime.inbox_mark_read(_T, "owner-1", "n-1", expected_revision=1)


def test_restart_continuity_same_config_dir(tmp_path) -> None:
    first = NotificationRuntime(tmp_path)
    first.inbox_store.create_or_replay(_rec())
    first.inbox_mark_read(_T, "owner-1", "n-1", expected_revision=1)
    # A fresh runtime over the same config dir resumes the durable rows.
    second = NotificationRuntime(tmp_path)
    got = second.inbox_get(_T, "owner-1", "n-1")
    assert got.revision == 2 and got.read_at is not None
