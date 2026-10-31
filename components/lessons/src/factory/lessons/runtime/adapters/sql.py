"""SQLStore adapter for durable owner-scoped lessons."""
from __future__ import annotations

import json
from datetime import datetime, timezone

from factory.storage.interface import SQLStore

from ..models import LessonRecord, LessonSource, LessonStatus
from .sql_rows import FIELDS, LESSON_SCHEMA, from_row, params


class SQLLessonStore:
    def __init__(self, sql: SQLStore) -> None:
        self._sql = sql
        sql.execute(LESSON_SCHEMA)

    def create(self, record: LessonRecord) -> LessonRecord:
        columns = ",".join(FIELDS)
        binds = ",".join(f":{field}" for field in FIELDS)
        try:
            self._sql.execute(
                f"INSERT INTO lessons ({columns}) VALUES ({binds})", params(record),
            )
            return record
        except Exception:
            existing = self.get_by_identity(
                record.tenant_id, record.owner_id, record.identity_key,
            )
            if existing == record:
                return existing
            raise

    def get(self, tenant_id: str, owner_id: str, lesson_id: str) -> LessonRecord | None:
        row = self._sql.fetch_one(
            "SELECT * FROM lessons WHERE tenant_id=:tenant AND owner_id=:owner "
            "AND lesson_id=:lesson",
            {"tenant": tenant_id, "owner": owner_id, "lesson": lesson_id},
        )
        return from_row(row)

    def get_by_identity(
        self, tenant_id: str, owner_id: str, identity_key: str,
    ) -> LessonRecord | None:
        row = self._sql.fetch_one(
            "SELECT * FROM lessons WHERE tenant_id=:tenant AND owner_id=:owner "
            "AND identity_key=:identity",
            {"tenant": tenant_id, "owner": owner_id, "identity": identity_key},
        )
        return from_row(row)

    def list(
        self, tenant_id: str, owner_id: str, limit: int = 100,
    ) -> list[LessonRecord]:
        rows = self._sql.fetch_all(
            "SELECT * FROM lessons WHERE tenant_id=:tenant AND owner_id=:owner "
            "ORDER BY updated_at DESC,lesson_id LIMIT :limit",
            {"tenant": tenant_id, "owner": owner_id,
             "limit": max(1, min(limit, 1000))},
        )
        return [record for row in rows if (record := from_row(row)) is not None]

    def enrich(
        self, record: LessonRecord, negative: str | None,
        evidence: tuple[str, ...], expected_revision: int,
    ) -> LessonRecord | None:
        now = datetime.now(timezone.utc)
        updated = record.model_copy(update={
            "negative": negative, "evidence": evidence,
            "revision": expected_revision + 1, "updated_at": now,
        })
        result = self._sql.execute(
            "UPDATE lessons SET negative=:negative,evidence=:evidence,"
            "revision=revision+1,updated_at=:updated WHERE tenant_id=:tenant "
            "AND owner_id=:owner AND lesson_id=:lesson AND revision=:revision",
            {"negative": negative, "evidence": json.dumps(
                 evidence, separators=(",", ":")),
             "updated": now.isoformat(), "tenant": record.tenant_id,
             "owner": record.owner_id, "lesson": record.lesson_id,
             "revision": expected_revision},
        )
        return updated if result.row_count == 1 else None

    def set_status(
        self, record: LessonRecord, status: LessonStatus, expected_revision: int,
    ) -> LessonRecord | None:
        now = datetime.now(timezone.utc)
        updated = record.model_copy(update={
            "status": status, "revision": expected_revision + 1,
            "updated_at": now,
        })
        result = self._sql.execute(
            "UPDATE lessons SET status=:status,revision=revision+1,updated_at=:updated "
            "WHERE tenant_id=:tenant AND owner_id=:owner AND lesson_id=:lesson "
            "AND revision=:revision",
            {"status": status.value, "updated": now.isoformat(),
             "tenant": record.tenant_id, "owner": record.owner_id,
             "lesson": record.lesson_id, "revision": expected_revision},
        )
        return updated if result.row_count == 1 else None

    def remove(
        self, tenant_id: str, owner_id: str, lesson_id: str,
        expected_revision: int,
    ) -> bool:
        result = self._sql.execute(
            "DELETE FROM lessons WHERE tenant_id=:tenant AND owner_id=:owner "
            "AND lesson_id=:lesson AND revision=:revision",
            {"tenant": tenant_id, "owner": owner_id,
             "lesson": lesson_id, "revision": expected_revision},
        )
        return result.row_count == 1

    def promote_explicit(
        self, record: LessonRecord, negative: str | None,
        evidence: tuple[str, ...], expected_revision: int,
    ) -> LessonRecord | None:
        now = datetime.now(timezone.utc)
        updated = record.model_copy(update={
            "source": LessonSource.USER_EXPLICIT, "confidence": 1.0,
            "status": LessonStatus.ACCEPTED, "negative": negative,
            "evidence": evidence, "revision": expected_revision + 1,
            "updated_at": now,
        })
        result = self._sql.execute(
            "UPDATE lessons SET source='user_explicit',confidence=1.0,status='accepted',"
            "negative=:negative,evidence=:evidence,revision=revision+1,updated_at=:updated "
            "WHERE tenant_id=:tenant AND owner_id=:owner AND lesson_id=:lesson "
            "AND revision=:revision AND source!='user_explicit'",
            {"negative": negative, "evidence": json.dumps(evidence, separators=(",", ":")),
             "updated": now.isoformat(), "tenant": record.tenant_id,
             "owner": record.owner_id, "lesson": record.lesson_id,
             "revision": expected_revision},
        )
        return updated if result.row_count == 1 else None

    def list_unprojected(self, limit: int = 100) -> list[LessonRecord]:
        rows = self._sql.fetch_all(
            "SELECT * FROM lessons WHERE status='accepted' AND memory_id IS NULL "
            "ORDER BY updated_at,lesson_id LIMIT :limit",
            {"limit": max(1, min(limit, 1000))},
        )
        return [record for row in rows if (record := from_row(row)) is not None]

    def mark_projected(
        self, record: LessonRecord, memory_id: str, expected_revision: int,
    ) -> LessonRecord | None:
        now = datetime.now(timezone.utc)
        updated = record.model_copy(update={
            "memory_id": memory_id, "memory_revision": record.revision,
            "revision": expected_revision + 1, "updated_at": now,
        })
        result = self._sql.execute(
            "UPDATE lessons SET memory_id=:memory,memory_revision=:memory_revision,"
            "revision=revision+1,updated_at=:updated WHERE tenant_id=:tenant "
            "AND owner_id=:owner AND lesson_id=:lesson AND revision=:revision "
            "AND status='accepted' AND memory_id IS NULL",
            {"memory": memory_id, "memory_revision": record.revision,
             "updated": now.isoformat(), "tenant": record.tenant_id,
             "owner": record.owner_id, "lesson": record.lesson_id,
             "revision": expected_revision},
        )
        return updated if result.row_count == 1 else None


__all__ = ["SQLLessonStore"]
