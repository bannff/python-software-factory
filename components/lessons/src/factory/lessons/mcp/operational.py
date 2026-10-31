"""Typed operational Lessons lifecycle tools."""
from __future__ import annotations

from typing import Any, Callable

from factory.mcp_utils.interface import (
    ToolResult, operational, protected_canonical_json, service_only,
)
from factory.mcp_utils.registration import typed_tool

from ..runtime.models import LessonCategory, LessonScope, LessonSource, LessonStatus
from .contracts import (
    AddLessonInput, LessonOutput, LessonRevisionInput,
    LessonWriteOutput, ProposalLessonInput, RemovedOutput,
)
from .events import emit_lesson_event
from .support import authority, verify_session


def register(mcp: Any, get_runtime: Callable[[], Any]) -> None:
    @typed_tool(mcp)
    @operational(input_model=AddLessonInput, output_model=LessonWriteOutput)
    async def lessons_add(
        rule: str, negative: str | None = None, category: str = "knowledge",
        scope: str = "global", scope_id: str | None = None,
        evidence: tuple[str, ...] = (), envelope: dict | None = None,
    ) -> ToolResult[LessonWriteOutput]:
        tenant, owner, thread, context = authority(envelope)
        await verify_session(thread, context)
        result = get_runtime().lifecycle.add(
            tenant, owner, rule, negative=negative,
            category=LessonCategory(category), scope=LessonScope(scope),
            scope_id=scope_id, evidence=evidence,
        )
        await emit_lesson_event(
            result.lesson, "lesson.accepted", outcome=result.outcome,
        )
        return LessonWriteOutput(result=result)

    @typed_tool(mcp)
    @service_only(callers={"events", "agent"}, binding="lesson_proposal")
    @operational(input_model=ProposalLessonInput, output_model=LessonWriteOutput)
    async def lessons_propose(
        tenant_id: str, owner_id: str, source_ref: str, proposal_digest: str,
        source: str, rule: str, negative: str | None = None,
        category: str = "knowledge", scope: str = "global",
        scope_id: str | None = None, evidence: tuple[str, ...] = (),
        confidence: float = 0.5,
    ) -> ToolResult[LessonWriteOutput]:
        material = {
            "tenant_id": tenant_id, "owner_id": owner_id,
            "source_ref": source_ref, "source": source, "rule": rule,
            "negative": negative, "category": category, "scope": scope,
            "scope_id": scope_id, "evidence": evidence,
            "confidence": confidence,
        }
        import hashlib
        actual = hashlib.sha256(protected_canonical_json(material)).hexdigest()
        if actual != proposal_digest:
            raise ValueError("lesson proposal digest mismatch")
        result = get_runtime().lifecycle.add(
            tenant_id, owner_id, rule, negative=negative,
            category=LessonCategory(category), scope=LessonScope(scope),
            scope_id=scope_id, evidence=evidence, source=LessonSource(source),
            source_ref=source_ref, confidence=confidence,
        )
        await emit_lesson_event(
            result.lesson, "lesson.proposed", outcome=result.outcome,
        )
        return LessonWriteOutput(result=result)

    def curate(name: str, status: LessonStatus):
        @typed_tool(mcp, name=name)
        @operational(input_model=LessonRevisionInput, output_model=LessonOutput)
        async def tool(
            lesson_id: str, expected_revision: int,
            envelope: dict | None = None,
        ) -> ToolResult[LessonOutput]:
            tenant, owner, thread, context = authority(envelope)
            await verify_session(thread, context)
            lesson = get_runtime().lifecycle.curate(
                tenant, owner, lesson_id, expected_revision, status,
            )
            await emit_lesson_event(lesson, f"lesson.{status.value}")
            return LessonOutput(lesson=lesson)
        return tool

    curate("lessons_accept", LessonStatus.ACCEPTED)
    curate("lessons_reject", LessonStatus.REJECTED)

    @typed_tool(mcp)
    @operational(input_model=LessonRevisionInput, output_model=RemovedOutput)
    async def lessons_remove(
        lesson_id: str, expected_revision: int,
        envelope: dict | None = None,
    ) -> ToolResult[RemovedOutput]:
        tenant, owner, thread, context = authority(envelope)
        await verify_session(thread, context)
        lesson = get_runtime().lifecycle.get(tenant, owner, lesson_id)
        get_runtime().lifecycle.remove(
            tenant, owner, lesson_id, expected_revision,
        )
        await emit_lesson_event(lesson, "lesson.removed")
        return RemovedOutput(lesson_id=lesson_id, removed=True)


__all__ = ["register"]
