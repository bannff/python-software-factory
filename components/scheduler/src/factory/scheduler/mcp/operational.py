"""Operational Scheduler MCP lifecycle tools."""
from __future__ import annotations

import asyncio
from typing import Any, Callable

from factory.mcp_utils.interface import ToolResult, fail, get_envelope, get_service, operational
from factory.mcp_utils.registration import typed_tool

from .contracts import (
    AddScheduleInput, FireOutput, RemovedOutput, RevisionInput, ScheduleOutput,
)
from .support import identity, owner_identity, result


def register(mcp: Any, get_runtime: Callable[[], Any]) -> None:
    @typed_tool(mcp)
    @operational(input_model=AddScheduleInput, output_model=ScheduleOutput)
    async def scheduler_add(agent_id: str, task: str, kind: str,
                            interval_seconds: int | None = None,
                            one_shot_at=None, cron_expression: str | None = None,
                            timezone_name: str = "UTC", skip_dates: tuple[str, ...] = (),
                            strict_schedule: bool = False,
                            output_schema: str | None = None,
                            delivery_mode: str = "origin",
                            loop_id: str | None = None, loop_cycle: int | None = None,
                            schedule_id: str | None = None,
                            envelope: dict | None = None) -> ToolResult[ScheduleOutput]:
        tenant, owner, thread = identity(envelope)
        origin = await _origin(thread, get_envelope() or envelope or {})
        return result(lambda: ScheduleOutput(schedule=get_runtime().lifecycle.create(
            tenant, owner, origin["session_id"], origin["thread_id"],
            agent_id, task, kind, interval_seconds=interval_seconds,
            one_shot_at=one_shot_at, cron_expression=cron_expression,
            timezone_name=timezone_name, skip_dates=skip_dates,
            strict_schedule=strict_schedule,
            output_schema=output_schema, delivery_mode=delivery_mode,
            loop_id=loop_id, loop_cycle=loop_cycle,
            schedule_id=schedule_id,
        )))

    @typed_tool(mcp)
    @operational(input_model=RevisionInput, output_model=ScheduleOutput)
    def scheduler_pause(schedule_id: str, expected_revision: int,
                        envelope: dict | None = None) -> ToolResult[ScheduleOutput]:
        tenant, owner = owner_identity(envelope)
        return result(lambda: ScheduleOutput(schedule=get_runtime().lifecycle.pause(
            tenant, owner, schedule_id, expected_revision,
        )))

    @typed_tool(mcp)
    @operational(input_model=RevisionInput, output_model=ScheduleOutput)
    def scheduler_resume(schedule_id: str, expected_revision: int,
                         envelope: dict | None = None) -> ToolResult[ScheduleOutput]:
        tenant, owner = owner_identity(envelope)
        return result(lambda: ScheduleOutput(schedule=get_runtime().lifecycle.resume(
            tenant, owner, schedule_id, expected_revision,
        )))

    @typed_tool(mcp)
    @operational(input_model=RevisionInput, output_model=RemovedOutput)
    def scheduler_remove(schedule_id: str, expected_revision: int,
                         envelope: dict | None = None) -> ToolResult[RemovedOutput]:
        tenant, owner = owner_identity(envelope)
        return result(lambda: _remove(
            get_runtime().lifecycle, tenant, owner, schedule_id, expected_revision,
        ))

    @typed_tool(mcp)
    @operational(input_model=RevisionInput, output_model=FireOutput)
    async def scheduler_trigger(
        schedule_id: str, expected_revision: int,
        envelope: dict | None = None,
    ) -> ToolResult[FireOutput]:
        tenant, owner = owner_identity(envelope)
        try:
            fire = await get_runtime().trigger(
                tenant, owner, schedule_id, expected_revision,
            )
            return result(lambda: FireOutput(fire=fire))
        except Exception:
            return fail("schedule_trigger_failed")


def _remove(lifecycle, tenant, owner, schedule_id, revision):
    lifecycle.remove(tenant, owner, schedule_id, revision)
    return RemovedOutput(removed=True, schedule_id=schedule_id)


async def _origin(thread_id: str, envelope: dict) -> dict:
    factory = get_service("tool_invoker_for_caller")
    invoke = factory("scheduler") if callable(factory) else None
    if not callable(invoke):
        raise ValueError("scheduler_origin_unavailable")
    raw = await asyncio.to_thread(
        invoke, {"brick_name": "session", "tool_name": "resolve_thread"},
        arguments={"thread_id": thread_id, "envelope": envelope},
        idempotency_key=f"scheduler-origin:{thread_id}", envelope=envelope,
    )
    structured = raw.get("result", {}).get("structured_content") if isinstance(raw, dict) else None
    data = structured.get("data") if isinstance(structured, dict) and structured.get("ok") else None
    if not isinstance(data, dict) or not isinstance(data.get("session"), dict):
        raise ValueError("scheduler_origin_not_found")
    return data["session"]


__all__ = ["register"]
