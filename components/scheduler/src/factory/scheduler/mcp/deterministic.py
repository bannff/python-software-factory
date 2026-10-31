"""Deterministic Scheduler MCP tools."""
from __future__ import annotations

from typing import Any, Callable

from factory.mcp_utils.interface import ToolResult, deterministic
from factory.mcp_utils.registration import typed_tool

from .contracts import (
    FireOutput, FireRefInput, ListSchedulesInput,
    ScheduleOutput, ScheduleRefInput, SchedulesOutput,
)
from .support import owner_identity, result


def register(mcp: Any, get_runtime: Callable[[], Any]) -> None:
    @typed_tool(mcp)
    @deterministic(input_model=ScheduleRefInput, output_model=ScheduleOutput)
    def scheduler_get(schedule_id: str, envelope: dict | None = None) -> ToolResult[ScheduleOutput]:
        tenant, owner = owner_identity(envelope)
        return result(lambda: ScheduleOutput(schedule=get_runtime().lifecycle.get(
            tenant, owner, schedule_id,
        )))

    @typed_tool(mcp)
    @deterministic(input_model=ListSchedulesInput, output_model=SchedulesOutput)
    def scheduler_list(envelope: dict | None = None) -> ToolResult[SchedulesOutput]:
        tenant, owner = owner_identity(envelope)
        return result(lambda: SchedulesOutput(
            schedules=get_runtime().lifecycle.list(tenant, owner),
        ))

    @typed_tool(mcp)
    @deterministic(input_model=FireRefInput, output_model=FireOutput)
    def scheduler_get_fire(schedule_id: str, fire_sequence: int,
                           envelope: dict | None = None) -> ToolResult[FireOutput]:
        tenant, owner = owner_identity(envelope)
        fire = get_runtime().lifecycle.store.get_fire(
            tenant, owner, schedule_id, fire_sequence,
        )
        return result(lambda: FireOutput(fire=fire) if fire else (_raise()))


def _raise():
    from ..runtime.errors import ScheduleNotFoundError
    raise ScheduleNotFoundError


__all__ = ["register"]
