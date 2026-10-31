"""Best-effort Scheduler observability through public MCP rails."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from factory.mcp_utils.interface import get_service

from .notification_projection import AutoPauseProjection

logger = logging.getLogger(__name__)


async def project_outcome(schedule: Any, fire: Any, state: str, auto_paused: bool) -> None:
    """Project terminal truth after its durable CAS; never gate scheduling."""
    envelope = _envelope(schedule)
    payload = {
        "schedule_id": schedule.schedule_id,
        "fire_sequence": fire.fire_sequence,
        "launch_id": fire.launch_id,
        "run_id": fire.workflow_run_id,
        "state": state,
        "auto_paused": auto_paused,
    }
    await _invoke(
        "events", "events_publish", envelope,
        arguments={
            "event_type": f"scheduler.fire.{state}", "payload": payload,
            "source": "scheduler", "tenant_id": schedule.tenant_id,
            "principal_id": schedule.owner_id,
            "session_id": schedule.origin_thread_id,
            "run_id_authoritative": True,
        },
        key=f"scheduler-event:{fire.launch_id}:{state}",
    )
    if auto_paused:
        projection = AutoPauseProjection(
            tenant_id=schedule.tenant_id, owner_id=schedule.owner_id,
            schedule_id=schedule.schedule_id, fire_sequence=fire.fire_sequence,
        )
        await _invoke(
            "notification", "inbox_publish", envelope,
            arguments=projection.arguments(),
            key=f"scheduler-auto-pause:{schedule.schedule_id}:{fire.fire_sequence}",
            projection=projection.binding(),
        )


async def _invoke(
    brick: str, tool: str, envelope: dict[str, str], *,
    arguments: dict[str, Any], key: str,
    projection: dict[str, Any] | None = None,
) -> None:
    try:
        factory = get_service("tool_invoker_for_caller")
        invoke = factory("scheduler") if callable(factory) else None
        if not callable(invoke):
            raise RuntimeError("caller-bound MCP unavailable")
        extra = {"projection": projection} if projection is not None else {}
        await asyncio.to_thread(
            invoke, {"brick_name": brick, "tool_name": tool},
            arguments=arguments, idempotency_key=key, envelope=envelope, **extra,
        )
    except Exception as exc:  # observability must not become schedule truth
        logger.warning("Scheduler %s projection failed: %s", brick, exc)


def _envelope(schedule: Any) -> dict[str, str]:
    return {
        "tenant_id": schedule.tenant_id,
        "principal_id": schedule.owner_id,
        "session_id": schedule.origin_thread_id,
    }


__all__ = ["project_outcome"]
