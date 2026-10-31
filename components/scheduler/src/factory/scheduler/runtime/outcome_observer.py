"""Workflow outcome observation for enrolled Scheduler fires."""
from __future__ import annotations

import asyncio
from typing import Any

from factory.mcp_utils.interface import get_service

from .models import FireState

_TERMINAL = {
    "succeeded": FireState.SUCCEEDED,
    "failed": FireState.FAILED,
    "cancelled": FireState.CANCELLED,
}


async def observe_outcomes(lifecycle: Any, limit: int = 100) -> tuple[str, ...]:
    settled = []
    for fire in lifecycle.store.list_enrolled(limit):
        schedule = lifecycle.get(fire.tenant_id, fire.owner_id, fire.schedule_id)
        status = await _workflow_status(schedule, fire.workflow_run_id or "")
        state = _TERMINAL.get(status)
        if state is None:
            continue
        updated = lifecycle.store.mark_outcome(fire, state, fire.revision)
        if updated is not None:
            from .observability import project_outcome
            current = lifecycle.get(fire.tenant_id, fire.owner_id, fire.schedule_id)
            await project_outcome(
                current, updated, state.value,
                current.state.value == "auto_paused",
            )
            settled.append(fire.workflow_run_id or "")
    return tuple(settled)


async def _workflow_status(schedule: Any, run_id: str) -> str:
    factory = get_service("tool_invoker_for_caller")
    invoke = factory("scheduler") if callable(factory) else None
    if not callable(invoke):
        raise RuntimeError("scheduler Workflow MCP unavailable")
    envelope = {
        "tenant_id": schedule.tenant_id, "principal_id": schedule.owner_id,
        "session_id": schedule.origin_thread_id,
    }
    raw = await asyncio.to_thread(
        invoke, {"brick_name": "workflow", "tool_name": "get_run"},
        arguments={"run_id": run_id, "envelope": envelope},
        idempotency_key=f"scheduler-observe:{run_id}", envelope=envelope,
    )
    structured = raw.get("result", {}).get("structured_content") if isinstance(raw, dict) else None
    data = structured.get("data") if isinstance(structured, dict) and structured.get("ok") else None
    if not isinstance(data, dict) or not isinstance(data.get("status"), str):
        raise RuntimeError("scheduler Workflow observation failed")
    return data["status"]


__all__ = ["observe_outcomes"]
