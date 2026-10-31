"""Exactly-once claimed-fire dispatch through typed MCP capability bindings."""
from __future__ import annotations

import asyncio
from typing import Any

from factory.mcp_utils.interface import get_service

from .models import FireState


async def replay_claimed(lifecycle: Any, limit: int = 100) -> tuple[str, ...]:
    dispatched = []
    for fire in lifecycle.store.list_claimed(limit):
        schedule = lifecycle.get(fire.tenant_id, fire.owner_id, fire.schedule_id)
        if schedule.delivery_mode == "maintenance":
            succeeded = await _run_maintenance(schedule, fire)
            run_id = f"maintenance-{fire.launch_id}"
            enrolled = lifecycle.store.mark_enrolled(fire, run_id, fire.revision)
            if enrolled is None:
                continue
            state = FireState.SUCCEEDED if succeeded else FireState.FAILED
            if lifecycle.store.mark_outcome(enrolled, state, enrolled.revision) is not None:
                dispatched.append(run_id)
            continue
        run_id = await _spawn_agent(schedule, fire)
        updated = lifecycle.store.mark_enrolled(fire, run_id, fire.revision)
        if updated is not None:
            dispatched.append(run_id)
    return tuple(dispatched)


async def _run_maintenance(schedule: Any, fire: Any) -> bool:
    if schedule.maintenance_target != "telemetry_retention":
        raise RuntimeError("unknown Scheduler maintenance target")
    raw = await _invoke(
        schedule, fire,
        {"brick_name": "telemetry", "tool_name": "telemetry_run_retention"},
        {},
    )
    structured = _structured(raw)
    return isinstance(structured, dict) and structured.get("ok") is True


async def _spawn_agent(schedule: Any, fire: Any) -> str:
    raw = await _invoke(
        schedule, fire,
        {"brick_name": "agent", "tool_name": "spawn_background"},
        {
            "agent_id": schedule.agent_id, "task": schedule.task,
            "launch_id": fire.launch_id,
            "output_schema": schedule.output_schema,
            "delivery_mode": schedule.delivery_mode,
            "loop_id": schedule.loop_id, "loop_cycle": schedule.loop_cycle,
        },
    )
    structured = _structured(raw)
    data = structured.get("data") if isinstance(structured, dict) and structured.get("ok") else None
    if not isinstance(data, dict) or not isinstance(data.get("run_id"), str):
        raise RuntimeError("scheduler Agent enrollment failed")
    return data["run_id"]


async def _invoke(schedule: Any, fire: Any, target: dict, arguments: dict) -> Any:
    factory = get_service("tool_invoker_for_caller")
    invoke = factory("scheduler") if callable(factory) else None
    if not callable(invoke):
        raise RuntimeError("scheduler typed MCP unavailable")
    envelope = {
        "tenant_id": schedule.tenant_id,
        "principal_id": schedule.owner_id,
        "session_id": schedule.origin_thread_id,
        "thread_id": schedule.origin_thread_id,
    }
    return await asyncio.to_thread(
        invoke, target, arguments=arguments,
        idempotency_key=f"scheduler-fire:{fire.launch_id}", envelope=envelope,
    )


def _structured(raw: Any) -> Any:
    return raw.get("result", {}).get("structured_content") if isinstance(raw, dict) else None


__all__ = ["replay_claimed"]
