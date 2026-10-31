"""Pure row projections shared by blockchain dashboard summaries."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def transaction_row(tx: dict[str, Any], activities: list[dict[str, Any]]) -> dict[str, Any]:
    age = age_minutes(str(tx.get("created_at", "")))
    return {
        **tx, "age_minutes": age, "age_label": age_label(age), "activity_count": len(activities),
        "last_activity_type": activities[0].get("event_type") if activities else "",
        "last_activity_label": activities[0].get("label") if activities else "",
        "entity_id": tx.get("tx_id", ""),
    }


def bounty_row(bounty: dict[str, Any], activities: list[dict[str, Any]]) -> dict[str, Any]:
    age = age_minutes(str(bounty.get("created_at", "")))
    return {
        **bounty, "age_minutes": age, "age_label": age_label(age), "activity_count": len(activities),
        "last_activity_type": activities[0].get("event_type") if activities else "",
        "last_activity_label": activities[0].get("label") if activities else "",
        "entity_id": bounty.get("bounty_id", ""),
    }


def age_minutes(timestamp: str) -> int:
    try:
        value = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return max(0, int((datetime.now(timezone.utc) - value).total_seconds() // 60))
    except ValueError:
        return 0


def age_label(age: int) -> str:
    if age < 1:
        return "just now"
    if age < 60:
        return f"{age}m"
    hours = age // 60
    if hours < 24:
        return f"{hours}h"
    return f"{hours // 24}d"
