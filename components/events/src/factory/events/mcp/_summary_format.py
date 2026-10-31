"""Time-formatting helpers for Events dashboard summaries."""

from __future__ import annotations

from datetime import datetime, timezone


def _age_minutes(timestamp: str) -> int:
    try:
        dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return max(0, int((datetime.now(timezone.utc) - dt).total_seconds() // 60))
    except ValueError:
        return 0


def _age_label(age_minutes: int) -> str:
    if age_minutes < 1:
        return "just now"
    if age_minutes < 60:
        return f"{age_minutes}m"
    hours = age_minutes // 60
    if hours < 24:
        return f"{hours}h"
    return f"{hours // 24}d"
