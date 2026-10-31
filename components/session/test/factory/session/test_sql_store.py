"""SQLStore-backed session and exactly-once steering tests."""
from __future__ import annotations

from datetime import datetime, timezone
import sqlite3
from uuid import uuid4

import pytest

from factory.session.runtime.adapters.sql import SQLSessionStore
from factory.session.runtime.models import SessionRecord, SteerMessage, SteerState
from factory.storage.interface import StorageRuntime

NOW = datetime.now(timezone.utc)
TENANT = "tenant:local"
OWNER = "svc:local"


def _adapter(tmp_path) -> SQLSessionStore:
    sql = StorageRuntime().get_sql_store(
        "sqlite", db_path=str(tmp_path / "sessions.db"),
    )
    return SQLSessionStore(sql)


def _session(session_id: str = "session_1") -> SessionRecord:
    return SessionRecord(
        tenant_id=TENANT, owner_id=OWNER, session_id=session_id,
        thread_id=f"thread_{session_id}", title="Session",
        agent_id="companion-x-default", model="openrouter",
        created_at=NOW, updated_at=NOW, revision=1,
    )


def _steer(*, delivery_id: str, send_id: str) -> SteerMessage:
    return SteerMessage(
        tenant_id=TENANT, owner_id=OWNER, session_id="session_1",
        delivery_id=delivery_id, send_id=send_id, content="new guidance",
        state=SteerState.WRITTEN, created_at=NOW, revision=1,
    )


def test_session_reads_are_owner_scoped(tmp_path) -> None:
    store = _adapter(tmp_path)
    record = store.create(_session())
    assert store.get(TENANT, OWNER, record.session_id) == record
    assert store.get(TENANT, "other", record.session_id) is None
    assert store.list(TENANT, OWNER) == [record]
    assert store.list(TENANT, "other") == []


def test_session_pins_are_durable_ordered_and_revision_fenced(tmp_path) -> None:
    store = _adapter(tmp_path)
    one = store.create(_session("session_1"))
    two = store.create(_session("session_2"))
    three = store.create(_session("session_3"))

    pinned_two = store.set_pinned(TENANT, OWNER, two.session_id, True, two.revision)
    pinned_one = store.set_pinned(TENANT, OWNER, one.session_id, True, one.revision)
    assert pinned_two is not None and pinned_one is not None
    assert [item.session_id for item in store.list(TENANT, OWNER)] == [
        "session_2", "session_1", "session_3",
    ]
    assert store.set_pinned(TENANT, OWNER, "session_1", False, 1) is None
    assert store.set_pinned(TENANT, "other", "session_1", False, 2) is None

    moved = store.move_pinned(
        TENANT, OWNER, "session_1", "session_2", pinned_one.revision,
    )
    assert moved is not None
    assert [item.session_id for item in store.list(TENANT, OWNER)] == [
        "session_1", "session_2", "session_3",
    ]
    tagged = store.set_tags(
        TENANT, OWNER, "session_1", ("urgent", "review"), moved.revision,
    )
    assert tagged is not None
    restarted = _adapter(tmp_path)
    assert restarted.get(TENANT, OWNER, "session_1").tags == ("urgent", "review")
    assert [item.session_id for item in restarted.list(TENANT, OWNER)][:2] == [
        "session_1", "session_2",
    ]
    archived = restarted.set_archived(
        TENANT, OWNER, "session_1", True, tagged.revision,
    )
    assert archived is not None and archived.pinned_rank is None
    assert three.pinned_rank is None


def test_session_revision_cas_and_archive(tmp_path) -> None:
    store = _adapter(tmp_path)
    store.create(_session())
    assert store.rename(TENANT, OWNER, "session_1", "wrong", 2) is None
    renamed = store.rename(TENANT, OWNER, "session_1", "Renamed", 1)
    assert renamed is not None and renamed.title == "Renamed"
    assert renamed.revision == 2
    archived = store.set_archived(TENANT, OWNER, "session_1", True, 2)
    assert archived is not None and archived.archived_at is not None
    assert store.list(TENANT, OWNER) == []
    assert store.list(TENANT, OWNER, include_archived=True) == [archived]


def test_steer_send_id_is_atomically_deduplicated(tmp_path) -> None:
    store = _adapter(tmp_path)
    store.create(_session())
    first = store.append(_steer(delivery_id="delivery_1", send_id="send_1"))
    duplicate = store.append(_steer(delivery_id="delivery_2", send_id="send_1"))
    assert duplicate.delivery_id == first.delivery_id
    assert duplicate.revision == first.revision == 1


def test_steer_transition_is_revision_fenced_and_owner_scoped(tmp_path) -> None:
    store = _adapter(tmp_path)
    store.create(_session())
    message = store.append(_steer(delivery_id=uuid4().hex, send_id="send_1"))
    assert store.list_written(TENANT, OWNER, "session_1") == [message]
    assert store.transition(
        TENANT, "other", message.session_id, message.delivery_id,
        SteerState.CONSUMED, 1,
    ) is None
    assert store.transition(
        TENANT, OWNER, message.session_id, message.delivery_id,
        SteerState.CONSUMED, 2,
    ) is None
    consumed = store.transition(
        TENANT, OWNER, message.session_id, message.delivery_id,
        SteerState.CONSUMED, 1,
    )
    assert consumed is not None and consumed.state is SteerState.CONSUMED
    assert consumed.revision == 2 and consumed.consumed_at is not None
    assert store.list_written(TENANT, OWNER, "session_1") == []
    assert store.transition(
        TENANT, OWNER, message.session_id, message.delivery_id,
        SteerState.REQUEUED, 2,
    ) is None


def test_archived_session_rejects_steer_append_and_transition(tmp_path) -> None:
    store = _adapter(tmp_path)
    store.create(_session())
    pending = store.append(_steer(delivery_id="delivery_1", send_id="send_1"))
    archived = store.set_archived(TENANT, OWNER, "session_1", True, 1)
    assert archived is not None
    with pytest.raises(ValueError, match="session not found"):
        store.append(_steer(delivery_id="delivery_2", send_id="send_2"))
    assert store.transition(
        TENANT, OWNER, "session_1", pending.delivery_id,
        SteerState.CONSUMED, pending.revision,
    ) is None


def test_thread_binding_is_unique_within_owner_scope(tmp_path) -> None:
    store = _adapter(tmp_path)
    first = store.create(_session())
    with pytest.raises(sqlite3.IntegrityError):
        store.create(first.model_copy(update={"session_id": "session_2"}))
    other_owner = first.model_copy(update={
        "owner_id": "other", "session_id": "session_2",
    })
    assert store.create(other_owner) == other_owner


def test_startup_reconciliation_requeues_written_once(tmp_path) -> None:
    store = _adapter(tmp_path)
    store.create(_session())
    written = store.append(_steer(delivery_id="delivery-crash", send_id="send-crash"))
    recovered = store.reconcile_written()
    assert [item.delivery_id for item in recovered] == [written.delivery_id]
    assert recovered[0].state is SteerState.REQUEUED
    assert recovered[0].revision == 2 and recovered[0].requeued_at is not None
    assert store.reconcile_written() == []


def test_session_runtime_reconciles_on_first_open(tmp_path, monkeypatch) -> None:
    from factory.session.runtime.runtime import SessionRuntime

    path = str(tmp_path / "runtime-restart.db")
    sql = StorageRuntime().get_sql_store("sqlite", db_path=path)
    store = SQLSessionStore(sql)
    store.create(_session())
    written = store.append(_steer(delivery_id="runtime-crash", send_id="runtime-send"))
    monkeypatch.setenv("COMPANION_X_SESSION_DB_PATH", path)
    runtime = SessionRuntime()
    recovered = runtime.lifecycle.get_steer(
        TENANT, OWNER, "session_1", written.delivery_id,
    )
    assert recovered.state is SteerState.REQUEUED
    assert recovered.revision == written.revision + 1
