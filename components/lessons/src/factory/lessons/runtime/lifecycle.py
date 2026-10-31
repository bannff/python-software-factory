"""Typed lesson insertion and exact-match enrichment lifecycle."""
from __future__ import annotations

from datetime import datetime, timezone

from .identity import lesson_identity
from .models import (
    LessonCategory, LessonRecord, LessonScope, LessonSource,
    LessonStatus, LessonWriteResult,
)
from .ports import LessonStore


class LessonConflictError(RuntimeError):
    pass


class LessonLifecycle:
    def __init__(self, store: LessonStore) -> None:
        self.store = store

    def add(
        self, tenant_id: str, owner_id: str, rule: str, *,
        negative: str | None = None,
        category: LessonCategory = LessonCategory.KNOWLEDGE,
        scope: LessonScope = LessonScope.GLOBAL,
        scope_id: str | None = None, evidence: tuple[str, ...] = (),
        source: LessonSource = LessonSource.USER_EXPLICIT,
        source_ref: str | None = None, confidence: float = 1.0,
    ) -> LessonWriteResult:
        identity, lesson_id = lesson_identity(
            tenant_id, owner_id, rule, scope.value, scope_id,
        )
        existing = self.store.get_by_identity(tenant_id, owner_id, identity)
        if existing is not None:
            return self._existing(existing, negative, evidence, source)
        now = datetime.now(timezone.utc)
        status = (LessonStatus.ACCEPTED if source is LessonSource.USER_EXPLICIT
                  else LessonStatus.PROPOSED)
        record = LessonRecord(
            tenant_id=tenant_id, owner_id=owner_id, lesson_id=lesson_id,
            identity_key=identity, rule=rule.strip(), negative=negative,
            category=category, scope=scope, scope_id=scope_id,
            source=source, source_ref=source_ref, evidence=evidence,
            confidence=confidence, status=status,
            created_at=now, updated_at=now,
        )
        return LessonWriteResult(
            outcome="inserted", reason="new_identity",
            lesson=self.store.create(record),
        )

    def _existing(
        self, record: LessonRecord, negative: str | None,
        evidence: tuple[str, ...], source: LessonSource,
    ) -> LessonWriteResult:
        chosen_negative = record.negative or negative
        merged = tuple(dict.fromkeys((*record.evidence, *evidence)))[:64]
        if source is LessonSource.USER_EXPLICIT and record.source is not source:
            promoted = self.store.promote_explicit(
                record, chosen_negative, merged, record.revision,
            )
            if promoted is None:
                raise LessonConflictError("lesson authority promotion conflict")
            return LessonWriteResult(
                outcome="enriched", reason="user_authority", lesson=promoted,
            )
        if record.source is LessonSource.USER_EXPLICIT and source is not record.source:
            return LessonWriteResult(
                outcome="deduped", reason="higher_authority", lesson=record,
            )
        if chosen_negative == record.negative and merged == record.evidence:
            reason = "kept_stored_clause" if negative and record.negative else "exact_match"
            return LessonWriteResult(
                outcome="unchanged", reason=reason, lesson=record,
            )
        updated = self.store.enrich(
            record, chosen_negative, merged, record.revision,
        )
        if updated is None:
            raise LessonConflictError("lesson enrichment revision conflict")
        return LessonWriteResult(
            outcome="enriched", reason="added_context", lesson=updated,
        )

    def get(self, tenant_id: str, owner_id: str, lesson_id: str) -> LessonRecord:
        record = self.store.get(tenant_id, owner_id, lesson_id)
        if record is None:
            raise ValueError("lesson_not_found")
        return record


    def curate(
        self, tenant_id: str, owner_id: str, lesson_id: str,
        expected_revision: int, status: LessonStatus,
    ) -> LessonRecord:
        record = self.get(tenant_id, owner_id, lesson_id)
        if record.revision != expected_revision or record.status is not LessonStatus.PROPOSED:
            raise LessonConflictError("lesson curation conflict")
        if status not in {LessonStatus.ACCEPTED, LessonStatus.REJECTED}:
            raise ValueError("invalid lesson curation status")
        updated = self.store.set_status(
            record, status, expected_revision,
        )
        if updated is None:
            raise LessonConflictError("lesson curation revision conflict")
        return updated

    def remove(
        self, tenant_id: str, owner_id: str, lesson_id: str,
        expected_revision: int,
    ) -> None:
        if self.store.remove(tenant_id, owner_id, lesson_id, expected_revision):
            return
        self.get(tenant_id, owner_id, lesson_id)
        raise LessonConflictError("lesson removal revision conflict")
    def list(self, tenant_id: str, owner_id: str, limit: int = 100) -> list[LessonRecord]:
        return self.store.list(tenant_id, owner_id, limit)


__all__ = ["LessonConflictError", "LessonLifecycle"]
