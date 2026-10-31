"""Workflow reconciliation of pending loop cycles into Scheduler one-shots."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from factory.mcp_utils.interface import get_service

from .loop_models import CycleState, LoopState
from .loop_sentinel import sentinel_exists


async def admit_pending(store: Any, allowed_root: Path, limit: int = 100) -> tuple[str, ...]:
    admitted = []
    for cycle in store.list_cycles(CycleState.PENDING, limit):
        loop = store.get_loop(cycle.tenant_id, cycle.owner_id, cycle.loop_id)
        if loop is None or loop.state is not LoopState.ACTIVE:
            continue
        stopped = sentinel_exists(loop.loop_id, Path(loop.project_root), allowed_root)
        from .loop_lifecycle import LoopLifecycle
        evaluated = LoopLifecycle(store).evaluate(
            loop, now=datetime.now(timezone.utc), sentinel_exists=stopped,
        )
        if evaluated.state is not LoopState.ACTIVE:
            continue
        schedule = await _schedule(loop, cycle)
        if schedule.get("schedule_id") != cycle.schedule_id:
            raise RuntimeError("loop scheduler binding mismatch")
        updated = store.set_cycle_state(
            cycle, CycleState.SCHEDULED, None, cycle.revision,
        )
        if updated is not None:
            admitted.append(cycle.schedule_id)
    return tuple(admitted)


async def _schedule(loop: Any, cycle: Any) -> dict[str, Any]:
    factory = get_service("tool_invoker_for_caller")
    invoke = factory("workflow") if callable(factory) else None
    if not callable(invoke):
        raise RuntimeError("workflow Scheduler MCP unavailable")
    envelope = loop.initiation_envelope.model_dump(mode="json")
    raw = await asyncio.to_thread(
        invoke, {"brick_name": "scheduler", "tool_name": "scheduler_add"},
        arguments={
            "agent_id": loop.agent_id, "task": _task(loop, cycle),
            "kind": "one_shot", "one_shot_at": cycle.scheduled_for.isoformat(),
            "output_schema": "loop-cycle-report-v1",
            "delivery_mode": "workflow_loop",
            "loop_id": loop.loop_id, "loop_cycle": cycle.cycle,
            "schedule_id": cycle.schedule_id, "envelope": envelope,
        },
        idempotency_key=f"workflow-loop-schedule:{loop.loop_id}:{cycle.cycle}",
        envelope=envelope,
    )
    structured = raw.get("result", {}).get("structured_content") if isinstance(raw, dict) else None
    data = structured.get("data") if isinstance(structured, dict) and structured.get("ok") else None
    schedule = data.get("schedule") if isinstance(data, dict) else None
    if not isinstance(schedule, dict):
        raise RuntimeError("loop Scheduler admission failed")
    if schedule.get("tenant_id") != loop.tenant_id or schedule.get("owner_id") != loop.owner_id:
        raise RuntimeError("loop Scheduler owner binding mismatch")
    return schedule


def _task(loop: Any, cycle: Any) -> str:
    return (
        f"[Workflow loop cycle {cycle.cycle}]\nObjective: {loop.objective}\n"
        f"Instructions: {loop.cycle_instructions}\n"
        "Read the configured north star, roadmap, and task ledger before acting. "
        "Advance one highest-leverage item, verify evidence, and return the exact "
        "loop-cycle-report-v1 structured output."
    )


__all__ = ["admit_pending"]
