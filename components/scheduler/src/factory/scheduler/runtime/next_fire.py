"""Timezone-aware interval, one-shot, and cron next-fire calculation."""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from croniter import croniter

from .models import ScheduleKind

_SKIP = re.compile(r"\d{4}-\d{2}-\d{2}")
_HORIZON = timedelta(days=731)


def next_fire(
    kind: ScheduleKind, *, created_at: datetime,
    interval_seconds: int | None = None, one_shot_at: datetime | None = None,
    cron_expression: str | None = None, timezone_name: str = "UTC",
    skip_dates: tuple[str, ...] = (), last_fire_at: datetime | None = None,
) -> datetime | None:
    zone = ZoneInfo(timezone_name)
    skipped = _skip_set(skip_dates)
    base = _utc(last_fire_at or created_at)
    if kind is ScheduleKind.ONE_SHOT:
        candidate = _utc(one_shot_at) if one_shot_at is not None else None
        return candidate if candidate and candidate.astimezone(zone).date() not in skipped else None
    expression = cron_expression if kind is ScheduleKind.CRON else None
    if kind is ScheduleKind.CRON:
        if not expression or len(expression.split()) != 5 or not croniter.is_valid(expression):
            raise ValueError("invalid five-field cron expression")
        iterator = croniter(expression, base.astimezone(zone))
    step = timedelta(seconds=max(60, int(interval_seconds or 0)))
    for _ in range(500_000):
        local = (iterator.get_next(datetime) if expression else
                 (base + step).astimezone(zone))
        candidate = _utc(local)
        if candidate - base > _HORIZON:
            return None
        if local.date() not in skipped:
            return candidate
        if not expression:
            base = candidate
    return None


def _skip_set(values: tuple[str, ...]) -> set[date]:
    result = set()
    for value in values:
        if _SKIP.fullmatch(value) is None:
            raise ValueError("skip dates must use YYYY-MM-DD")
        result.add(date.fromisoformat(value))
    return result


def _utc(value: datetime | None) -> datetime:
    if value is None or value.tzinfo is None:
        raise ValueError("schedule timestamps must be timezone-aware")
    return value.astimezone(timezone.utc)


__all__ = ["next_fire"]
