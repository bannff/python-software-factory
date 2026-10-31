"""Owner-scoped materialization of one paused imported schedule.

The migration control plane hands the Scheduler a target-owned schedule
definition plus a recomputed content digest. This module recomputes the
canonical digest before any effect, derives a stable source-record schedule
identity, and persists the schedule directly in the paused state so an import
can never briefly become active.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from factory.mcp_utils.interface import protected_canonical_json

from .adapters.sql_rows import same_schedule_spec
from .lifecycle import SchedulerLifecycle
from .models import ScheduleKind, ScheduleRecord, ScheduleState


@dataclass(frozen=True, slots=True)
class ImportResult:
    schedule: ScheduleRecord
    imported: bool
    replayed: bool


def derive_schedule_id(source_adapter: str, source_record_id: str) -> str:
    """Stable, collision-resistant identity from the immutable source record."""
    seed = f"{source_adapter}\x00{source_record_id}".encode()
    return f"mig_{hashlib.sha256(seed).hexdigest()[:40]}"


def canonical_target(
    tenant_id: str, owner_id: str, schedule_id: str, definition: dict[str, Any],
) -> dict[str, Any]:
    """The target-owned payload the digest commits to, ahead of any effect."""
    return {
        "tenant_id": tenant_id, "owner_id": owner_id,
        "schedule_id": schedule_id, "definition": definition,
    }


def target_digest(
    tenant_id: str, owner_id: str, schedule_id: str, definition: dict[str, Any],
) -> str:
    payload = canonical_target(tenant_id, owner_id, schedule_id, definition)
    return hashlib.sha256(protected_canonical_json(payload)).hexdigest()


def import_paused_schedule(
    lifecycle: SchedulerLifecycle, *, tenant_id: str, owner_id: str,
    source_adapter: str, source_record_id: str, expected_digest: str,
    definition: dict[str, Any], origin_session_id: str, origin_thread_id: str,
) -> ImportResult:
    """Recompute the digest, then idempotently persist a paused schedule."""
    schedule_id = derive_schedule_id(source_adapter, source_record_id)
    if target_digest(tenant_id, owner_id, schedule_id, definition) != expected_digest:
        raise ValueError("scheduler_import_digest_mismatch")
    record = _paused_record(
        tenant_id, owner_id, schedule_id, definition,
        origin_session_id, origin_thread_id)
    existing = lifecycle.store.get(tenant_id, owner_id, schedule_id)
    if existing is not None:
        if same_schedule_spec(existing, record):
            return ImportResult(existing, imported=False, replayed=True)
        raise ValueError("scheduler_import_conflict")
    created = lifecycle.store.create(record)
    if same_schedule_spec(created, record):
        return ImportResult(created, imported=created.revision == 1,
                            replayed=created.revision != 1)
    raise ValueError("scheduler_import_conflict")


def _paused_record(
    tenant_id: str, owner_id: str, schedule_id: str, definition: dict[str, Any],
    origin_session_id: str, origin_thread_id: str,
) -> ScheduleRecord:
    now = datetime.now(timezone.utc)
    kind = ScheduleKind(definition["kind"])
    return ScheduleRecord(
        tenant_id=tenant_id, owner_id=owner_id, schedule_id=schedule_id,
        origin_session_id=origin_session_id, origin_thread_id=origin_thread_id,
        agent_id=definition["agent_id"], task=definition["task"], kind=kind,
        interval_seconds=definition.get("interval_seconds")
        if kind is ScheduleKind.INTERVAL else None,
        one_shot_at=definition.get("one_shot_at")
        if kind is ScheduleKind.ONE_SHOT else None,
        cron_expression=definition.get("cron_expression")
        if kind is ScheduleKind.CRON else None,
        timezone=definition.get("timezone_name", "UTC"),
        skip_dates=tuple(definition.get("skip_dates", ())),
        strict_schedule=bool(definition.get("strict_schedule", False)),
        delivery_mode="origin",
        state=ScheduleState.PAUSED, next_fire_at=None,
        created_at=now, updated_at=now, revision=1,
    )


__all__ = [
    "ImportResult", "canonical_target", "derive_schedule_id",
    "import_paused_schedule", "target_digest",
]
