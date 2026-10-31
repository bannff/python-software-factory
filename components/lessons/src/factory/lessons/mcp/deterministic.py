"""Typed deterministic Lessons read tools."""
from __future__ import annotations

from typing import Any, Callable

from factory.mcp_utils.interface import ToolResult, deterministic
from factory.mcp_utils.registration import typed_tool

from .contracts import (
    LessonOutput, LessonRefInput, LessonsOutput, ListLessonsInput,
    RecallInput, RecallItem, RecallOutput,
)
from .support import owner_authority


def register(mcp: Any, get_runtime: Callable[[], Any]) -> None:
    @typed_tool(mcp)
    @deterministic(input_model=LessonRefInput, output_model=LessonOutput)
    def lessons_get(
        lesson_id: str, envelope: dict | None = None,
    ) -> ToolResult[LessonOutput]:
        tenant, owner, _ = owner_authority(envelope)
        return LessonOutput(lesson=get_runtime().lifecycle.get(
            tenant, owner, lesson_id,
        ))

    @typed_tool(mcp)
    @deterministic(input_model=ListLessonsInput, output_model=LessonsOutput)
    def lessons_list(
        limit: int = 100, envelope: dict | None = None,
    ) -> ToolResult[LessonsOutput]:
        tenant, owner, _ = owner_authority(envelope)
        return LessonsOutput(lessons=get_runtime().lifecycle.list(
            tenant, owner, limit,
        ))

    @typed_tool(mcp)
    @deterministic(input_model=RecallInput, output_model=RecallOutput)
    async def lessons_recall(
        query: str, persona_id: str, limit: int = 8,
        envelope: dict | None = None,
    ) -> ToolResult[RecallOutput]:
        tenant, owner, _ = owner_authority(envelope)
        lessons = await get_runtime().recall(
            tenant, owner, persona_id, query, limit,
        )
        return RecallOutput(lessons=[RecallItem.model_validate(
            item.model_dump(mode="json"),
        ) for item in lessons])


__all__ = ["register"]
