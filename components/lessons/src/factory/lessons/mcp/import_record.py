"""Protected Migration→Lessons import of one user-authored lesson.

Registered only for the trusted in-process ``migration`` caller under the
``migration_import`` binding. The import replays the KiroCrew lesson into the
factory Lessons brick as a user-authored ACCEPTED record — no synthetic active
Session is required — while preserving the brick's exact normalized identity
and merge-enrichment semantics (never semantic-overlap or newer-wins deletion).
Source identity is carried in ``source_ref`` so replays land idempotently.
"""
from __future__ import annotations

from typing import Any, Callable

from factory.mcp_utils.interface import (
    ToolResult, get_envelope, operational, service_only,
)
from factory.mcp_utils.registration import typed_tool

from ..runtime.identity import import_scope, import_target_digest
from ..runtime.models import LessonCategory, LessonScope, LessonSource
from .contracts import ImportLessonInput, ImportLessonOutput
from .events import emit_lesson_event


def register(mcp: Any, get_runtime: Callable[[], Any]) -> None:
    @typed_tool(mcp)
    @service_only(callers={"migration"}, binding="migration_import")
    @operational(input_model=ImportLessonInput, output_model=ImportLessonOutput)
    async def lessons_import_record(
        tenant_id: str, owner_id: str, source_adapter: str,
        source_fingerprint: str, plan_digest: str, kind: str,
        source_record_id: str, target_digest: str, rule: str,
        negative: str | None = None, category: str = "knowledge",
        repo_scope: str = "", evidence: tuple[str, ...] = (),
    ) -> ToolResult[ImportLessonOutput]:
        ambient = get_envelope() or {}
        if ambient.get("tenant_id") != tenant_id \
                or ambient.get("principal_id") != owner_id:
            raise ValueError("lessons_import_authority_mismatch")
        if kind != "lessons":
            raise ValueError("lessons_import_kind_unsupported")
        scope_name, scope_id = import_scope(repo_scope)
        expected = import_target_digest(
            tenant_id, owner_id, source_adapter, source_record_id, rule,
            negative, category, repo_scope, tuple(evidence),
        )
        if expected != target_digest:
            raise ValueError("lessons_import_target_digest_mismatch")
        result = get_runtime().lifecycle.add(
            tenant_id, owner_id, rule, negative=negative,
            category=LessonCategory(category), scope=LessonScope(scope_name),
            scope_id=scope_id, evidence=tuple(evidence),
            source=LessonSource.USER_EXPLICIT,
            source_ref=f"{source_adapter}:{source_record_id}", confidence=1.0,
        )
        replayed = result.outcome in {"unchanged", "deduped"}
        if result.lesson is not None:
            await emit_lesson_event(
                result.lesson, "lesson.accepted", outcome=result.outcome,
            )
        return ImportLessonOutput(
            imported=not replayed, replayed=replayed,
            outcome=result.outcome, lesson=result.lesson,
        )


__all__ = ["register"]
