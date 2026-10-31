"""Runtime-level tests for the trusted inbox projection (persist-before-deliver).

Exercises :func:`project_notification` directly (the MCP service-only rail is
covered in ``test_inbox_publish_service_only``): digest recompute, closed
schedule target, create_or_replay ordering before delivery, delivery failure
leaving inbox truth intact, exact replay with no redelivery, dedupe conflict
with no delivery, and restart continuity over the same durable DB.
"""
from __future__ import annotations

import asyncio

import pytest
from pydantic import ValidationError

from factory.notification.mcp.contracts.inbox_publish import InboxPublishInput
from factory.notification.runtime.adapters.inbox_store_sql import SqlInboxStore
from factory.notification.runtime.dispatcher import NotificationRuntime
from factory.notification.runtime.inbox_models import InboxCommit, NotificationRecord
from factory.notification.runtime.inbox_projection import (
    ProjectionConflictError, ProjectionDigestError, material_digest,
    project_notification,
)
from factory.notification.runtime.inbox_targets import target_id, target_kind

_T, _OWNER, _SID = "tenant-1", "owner-1", "nightly"
_DK = "scheduler-auto-pause:nightly:5"
_TITLE = "Schedule auto-paused"
_BODY = "Schedule nightly was auto-paused after five consecutive failed runs."


def _digest(**over) -> str:
    base = dict(event_type="scheduler.schedule.auto_paused", subject_id=_SID,
                revision=5, dedupe_key=_DK, priority="critical", title=_TITLE,
                body=_BODY)
    base.update(over)
    return material_digest(**base)


def _kwargs(**over) -> dict:
    base = dict(tenant_id=_T, owner_id=_OWNER,
                event_type="scheduler.schedule.auto_paused", subject_id=_SID,
                revision=5, payload_digest=_digest(), dedupe_key=_DK,
                priority="critical", title=_TITLE, body=_BODY)
    base.update(over)
    return base


async def _runtime(tmp_path) -> NotificationRuntime:
    runtime = NotificationRuntime(tmp_path)
    await runtime.initialize()
    return runtime


def test_digest_mismatch_fails_closed_without_persisting(tmp_path) -> None:
    runtime = asyncio.run(_runtime(tmp_path))
    with pytest.raises(ProjectionDigestError):
        asyncio.run(project_notification(runtime, **_kwargs(payload_digest="0" * 64)))
    assert runtime.inbox_list(_T, _OWNER, limit=10) == []


def test_input_rejects_arbitrary_url_target() -> None:
    with pytest.raises(ValidationError):
        InboxPublishInput.model_validate(_kwargs(subject_id="http://evil/x"))


def test_persist_precedes_delivery_and_target_is_schedule(tmp_path) -> None:
    runtime = asyncio.run(_runtime(tmp_path))
    order: list[str] = []
    real_create = runtime.inbox_store.create_or_replay

    def spy_create(record: NotificationRecord) -> InboxCommit:
        order.append("persist")
        return real_create(record)

    async def spy_send(**_):
        order.append("deliver")
        return {"ok": True, "status": "sent"}

    runtime.inbox_store.create_or_replay = spy_create  # type: ignore[method-assign]
    runtime.send_notification = spy_send  # type: ignore[method-assign]
    outcome = asyncio.run(project_notification(runtime, **_kwargs()))
    assert order == ["persist", "deliver"]
    assert outcome.persisted and outcome.status == "created"
    assert outcome.delivery == "delivered"
    stored = runtime.inbox_get(_T, _OWNER, outcome.notification_id)
    assert target_kind(stored.target) == "schedule" and target_id(stored.target) == _SID


def test_delivery_failure_leaves_inbox_truth(tmp_path) -> None:
    runtime = asyncio.run(_runtime(tmp_path))

    async def boom(**_):
        raise RuntimeError("provider secret: token=super-secret")

    runtime.send_notification = boom  # type: ignore[method-assign]
    outcome = asyncio.run(project_notification(runtime, **_kwargs()))
    assert outcome.persisted and outcome.status == "created"
    assert outcome.delivery == "failed"
    stored = runtime.inbox_get(_T, _OWNER, outcome.notification_id)
    assert stored.title == _TITLE and stored.read_at is None


def test_exact_replay_returns_same_record_without_redelivery(tmp_path) -> None:
    runtime = asyncio.run(_runtime(tmp_path))
    sends = []

    async def count_send(**_):
        sends.append(1)
        return {"ok": True, "status": "sent"}

    runtime.send_notification = count_send  # type: ignore[method-assign]
    first = asyncio.run(project_notification(runtime, **_kwargs()))
    second = asyncio.run(project_notification(runtime, **_kwargs()))
    assert first.status == "created" and second.status == "replayed"
    assert second.delivery == "skipped"
    assert second.notification_id == first.notification_id
    assert sends == [1]  # replay must not redeliver


def test_dedupe_conflict_fails_closed_and_never_delivers(tmp_path) -> None:
    runtime = asyncio.run(_runtime(tmp_path))
    sends = []

    async def count_send(**_):
        sends.append(1)
        return {"ok": True, "status": "sent"}

    runtime.send_notification = count_send  # type: ignore[method-assign]
    asyncio.run(project_notification(runtime, **_kwargs()))
    body2 = _BODY + " (edited)"  # same dedupe key, different bound content
    with pytest.raises(ProjectionConflictError):
        asyncio.run(project_notification(
            runtime, **_kwargs(body=body2, payload_digest=_digest(body=body2))))
    assert sends == [1]  # only the first CREATED delivered


def test_restart_over_same_db_replays_not_reconflicts(tmp_path) -> None:
    db = str(tmp_path / "inbox.db")
    runtime = NotificationRuntime(tmp_path, inbox_store=SqlInboxStore(db_path=db))
    asyncio.run(runtime.initialize())

    async def send_ok(**_):
        return {"ok": True, "status": "sent"}

    runtime.send_notification = send_ok  # type: ignore[method-assign]
    first = asyncio.run(project_notification(runtime, **_kwargs()))
    reborn = NotificationRuntime(tmp_path, inbox_store=SqlInboxStore(db_path=db))
    asyncio.run(reborn.initialize())
    reborn.send_notification = send_ok  # type: ignore[method-assign]
    again = asyncio.run(project_notification(reborn, **_kwargs()))
    assert first.status == "created" and again.status == "replayed"
    assert again.notification_id == first.notification_id
