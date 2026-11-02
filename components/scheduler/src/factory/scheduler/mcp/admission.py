"""Admission rules for a *new* schedule, with typed ``scheduler_*`` failures.

These live at the tool boundary, not in the lifecycle: importing or replaying
existing records legitimately carries past times, so only creation is held to
"will this ever run?".
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from factory.mcp_utils.interface import get_service

MIN_INTERVAL_SECONDS = 60  # the scheduler polls on a coarse tick


def check_fields(
    task: str, kind: str, interval_seconds: int | None, one_shot_at: Any,
    now: datetime | None = None,
) -> None:
    if not task.strip():
        raise ValueError("scheduler_task_required")
    if kind == "interval" and (interval_seconds or 0) < MIN_INTERVAL_SECONDS:
        raise ValueError("scheduler_interval_too_short")
    if kind == "one_shot" and isinstance(one_shot_at, datetime):
        moment = one_shot_at if one_shot_at.tzinfo else one_shot_at.replace(tzinfo=timezone.utc)
        if moment <= (now or datetime.now(timezone.utc)):
            raise ValueError("scheduler_one_shot_in_past")


async def check_agent(agent_id: str, envelope: dict[str, Any]) -> None:
    """Reject an agent id the registry does not know (opaque when no invoker)."""
    factory = get_service("tool_invoker_for_caller")
    invoke = factory("scheduler") if callable(factory) else None
    if not callable(invoke):
        return
    raw = await asyncio.to_thread(
        invoke, {"brick_name": "agent", "tool_name": "get_agent_registry"},
        arguments={}, idempotency_key=f"scheduler-agent:{agent_id}:{uuid4().hex}",
        envelope=envelope,
    )
    structured = raw.get("result", {}).get("structured_content") if isinstance(raw, dict) else None
    data = structured.get("data") if isinstance(structured, dict) and structured.get("ok") else None
    agents = data.get("agents") if isinstance(data, dict) else None
    if isinstance(agents, list) and agent_id not in {a.get("id") for a in agents if isinstance(a, dict)}:
        raise ValueError("scheduler_agent_not_found")


__all__ = ["MIN_INTERVAL_SECONDS", "check_agent", "check_fields"]
