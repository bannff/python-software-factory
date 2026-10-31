"""Trusted producer projection: persist-before-deliver into the durable inbox.

The projection recomputes the content/material digest *before* any effect, then
calls :meth:`InboxStore.create_or_replay` FIRST and only attempts best-effort
channel delivery after a first-time ``CREATED`` commit. An exact ``REPLAYED``
never redelivers; a dedupe ``CONFLICT`` fails closed and never delivers. The
notification identity is derived from ``(tenant, owner, dedupe_key)`` so it is
stable across retries; ``created_at`` is excluded from the store dedupe digest,
so its wall-clock value never provokes a replay conflict.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict

from factory.mcp_utils.interface import protected_canonical_json

from .inbox_models import (
    InboxAdapterError, InboxCommitStatus, NotificationRecord, Priority,
)
from .inbox_targets import ScheduleTarget


class ProjectionConflictError(InboxAdapterError):
    """Dedupe key already holds different content — never overwritten/delivered."""

    def __init__(self) -> None:
        super().__init__("notification projection content conflict")


class ProjectionDigestError(InboxAdapterError):
    """Recomputed content digest did not match the bound producer digest."""

    def __init__(self) -> None:
        super().__init__("notification projection digest mismatch")


class InboxProjectionOutcome(BaseModel):
    """Result of one projection: durable truth plus delivery disposition."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    persisted: bool
    status: str            # "created" | "replayed"
    notification_id: str
    delivery: str          # "delivered" | "skipped" | "failed"


def material_digest(
    *, event_type: str, subject_id: str, revision: int, dedupe_key: str,
    priority: str, title: str, body: str,
) -> str:
    """Deterministic content/material digest bound by the trusted producer."""
    canonical = protected_canonical_json({
        "brick": "scheduler", "event_type": event_type,
        "target_kind": "schedule", "target_id": subject_id,
        "schedule_id": subject_id, "fire_sequence": revision,
        "dedupe_key": dedupe_key, "priority": priority,
        "title": title, "body": body,
    })
    return hashlib.sha256(canonical).hexdigest()


def _notification_id(tenant_id: str, owner_id: str, dedupe_key: str) -> str:
    seed = protected_canonical_json({
        "tenant_id": tenant_id, "owner_id": owner_id, "dedupe_key": dedupe_key,
    })
    return "ntf_" + hashlib.sha256(seed).hexdigest()[:32]


async def project_notification(
    runtime, *, tenant_id: str, owner_id: str, event_type: str, subject_id: str,
    revision: int, payload_digest: str, dedupe_key: str, priority: str,
    title: str, body: str,
) -> InboxProjectionOutcome:
    """Recompute digest, persist first, then best-effort deliver on CREATED."""
    if material_digest(
        event_type=event_type, subject_id=subject_id, revision=revision,
        dedupe_key=dedupe_key, priority=priority, title=title, body=body,
    ) != payload_digest:
        raise ProjectionDigestError()
    record = NotificationRecord(
        tenant_id=tenant_id, owner_id=owner_id,
        notification_id=_notification_id(tenant_id, owner_id, dedupe_key),
        kind="scheduler_auto_paused", title=title, body=body,
        priority=Priority(priority), target=ScheduleTarget(schedule_id=subject_id),
        dedupe_key=dedupe_key, created_at=datetime.now(timezone.utc),
    )
    commit = runtime.inbox_store.create_or_replay(record)  # persist FIRST
    if commit.status is InboxCommitStatus.CONFLICT:
        raise ProjectionConflictError()                    # fail closed, no delivery
    if commit.status is InboxCommitStatus.REPLAYED:
        return InboxProjectionOutcome(
            persisted=True, status="replayed",
            notification_id=commit.record.notification_id, delivery="skipped")
    preferences = runtime.prefs_get(tenant_id, owner_id)
    deliver, priority_override = preferences.effective_delivery(
        commit.record.kind, commit.record.priority)
    if not deliver:
        delivery = "skipped_muted"
    else:
        delivery = await _deliver(runtime, commit.record, priority_override)
    return InboxProjectionOutcome(
        persisted=True, status="created",
        notification_id=commit.record.notification_id, delivery=delivery)


async def _deliver(
    runtime, record: NotificationRecord, effective_priority: Priority,
) -> str:
    """Best-effort channel delivery; failure never mutates inbox truth."""
    delivery_priority = {
        Priority.PASSIVE: "low", Priority.DEFAULT: "normal",
        Priority.CRITICAL: "high",
    }[effective_priority]
    try:
        result = await runtime.send_notification(
            recipient=record.owner_id, content=record.body or None,
            subject=record.title, priority=delivery_priority)
    except Exception:  # noqa: BLE001 — no raw provider error escapes the inbox truth
        return "failed"
    delivered = bool(result.get("ok")) and result.get("status") != "failed"
    return "delivered" if delivered else "failed"


__all__ = [
    "InboxProjectionOutcome", "ProjectionConflictError", "ProjectionDigestError",
    "material_digest", "project_notification",
]
