"""Prepare exact protected target calls from immutable Migration records."""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from factory.mcp_utils.interface import protected_canonical_json

from .plan_records import PlanRecord
from .source_models import SafeLesson, SafeMarkdown, SafeMemory, SafeSchedule, SourceKind
from .target_contracts import (
    LessonTargetArgs, MemoryTargetArgs, PreparedTargetCall,
    ScheduleTargetDefinition, SchedulerTargetArgs,
)

_ERROR = "migration_target_record_unsupported"
_CATEGORIES = frozenset({"tool", "preference", "knowledge"})


class TargetPreparationError(ValueError):
    """Fixed content-free refusal for a record unsupported by target ingress."""

    def __init__(self) -> None:
        super().__init__(_ERROR)
        self.safe = _ERROR


def _identity(record: PlanRecord, kind: str, target_digest: str) -> dict[str, str]:
    digest = record.plan_digest.removeprefix("sha256:")
    if len(digest) != 64:
        raise TargetPreparationError
    return {
        "tenant_id": record.tenant_id, "owner_id": record.owner_id,
        "source_adapter": record.adapter,
        "source_fingerprint": record.source_fingerprint,
        "plan_digest": digest, "kind": kind,
        "source_record_id": record.source_record_id,
        "target_digest": target_digest,
    }


def _digest(material: dict) -> str:
    return hashlib.sha256(protected_canonical_json(material)).hexdigest()


def _memory(record: PlanRecord, payload: SafeMemory | SafeMarkdown) -> PreparedTargetCall:
    if isinstance(payload, SafeMarkdown):
        subtype = "semantic"
        key = f"markdown:{payload.doc}:{record.source_record_id}"
        tags = ("kirocrew-import", "markdown", payload.doc)
    else:
        subtype = payload.kind
        key = payload.key or ""
        tags = tuple(sorted(set(payload.tags)))
    material = {
        "tenant_id": record.tenant_id, "owner_id": record.owner_id,
        "kind": "memory", "subtype": subtype, "content": payload.content,
        "key": key, "tags": sorted(set(tags)),
    }
    args = MemoryTargetArgs(**{
        **_identity(record, "memory", _digest(material)),
        "subtype": subtype, "content": payload.content, "key": key, "tags": list(tags),
    })
    return PreparedTargetCall(
        source_kind=record.kind, brick="memory", tool="memory_import_record",
        arguments=args,
    )


def _lesson(record: PlanRecord, payload: SafeLesson) -> PreparedTargetCall:
    category = payload.category if payload.category in _CATEGORIES else "knowledge"
    scope, scope_id = (("persona", payload.repo_scope)
                       if payload.repo_scope else ("global", None))
    normalized = payload.rule.lower().strip()
    identity_key = _digest({
        "tenant_id": record.tenant_id, "owner_id": record.owner_id,
        "rule": normalized, "scope": scope, "scope_id": scope_id,
    })
    material = {
        "source_adapter": record.adapter,
        "source_record_id": record.source_record_id,
        "identity_key": identity_key, "lesson_id": f"les_{identity_key[:32]}",
        "rule": normalized, "negative": payload.negative,
        "category": category, "scope": scope, "scope_id": scope_id,
        "evidence": [],
    }
    args = LessonTargetArgs(**{
        **_identity(record, "lessons", _digest(material)),
        "rule": payload.rule, "negative": payload.negative,
        "category": category, "repo_scope": payload.repo_scope, "evidence": (),
    })
    return PreparedTargetCall(
        source_kind=SourceKind.LESSONS, brick="lessons",
        tool="lessons_import_record", arguments=args,
    )


def _one_shot(value: float | None) -> datetime:
    try:
        if value is None:
            raise ValueError
        return datetime.fromtimestamp(value, tz=timezone.utc)
    except (OverflowError, OSError, ValueError) as exc:
        raise TargetPreparationError from exc


def _schedule(record: PlanRecord, payload: SafeSchedule) -> PreparedTargetCall:
    mapped = {"every": "interval", "at": "one_shot", "cron": "cron"}[payload.schedule_kind]
    definition = ScheduleTargetDefinition(
        task=payload.message or payload.name,
        agent_id=payload.agent_id or "companion-x-default", kind=mapped,
        interval_seconds=payload.every_secs if mapped == "interval" else None,
        one_shot_at=_one_shot(payload.at_ts) if mapped == "one_shot" else None,
        cron_expression=payload.cron_expr if mapped == "cron" else None,
        timezone_name=payload.timezone or "UTC", skip_dates=payload.skip_dates,
        strict_schedule=payload.strict_schedule,
    )
    schedule_id = "mig_" + hashlib.sha256(
        f"{record.adapter}\x00{record.source_record_id}".encode()).hexdigest()[:40]
    definition_json = definition.model_dump(mode="json")
    target = _digest({
        "tenant_id": record.tenant_id, "owner_id": record.owner_id,
        "schedule_id": schedule_id, "definition": definition_json,
    })
    args = SchedulerTargetArgs(**{
        **_identity(record, "schedules", target), "schedule": definition,
    })
    return PreparedTargetCall(
        source_kind=SourceKind.SCHEDULES, brick="scheduler",
        tool="scheduler_import_record", arguments=args,
    )


def prepare_target_call(record: PlanRecord) -> PreparedTargetCall:
    """Build one target-owned call or return a fixed safe unsupported error."""
    try:
        payload = record.payload
        if isinstance(payload, (SafeMemory, SafeMarkdown)):
            return _memory(record, payload)
        if isinstance(payload, SafeLesson):
            return _lesson(record, payload)
        if isinstance(payload, SafeSchedule):
            return _schedule(record, payload)
    except TargetPreparationError:
        raise
    except (TypeError, ValueError) as exc:
        raise TargetPreparationError from exc
    raise TargetPreparationError


__all__ = ["TargetPreparationError", "prepare_target_call"]
