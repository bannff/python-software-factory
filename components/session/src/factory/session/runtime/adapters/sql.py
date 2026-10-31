"""SQLStore adapter for tenant-owned sessions and steer delivery."""
from __future__ import annotations

from typing import Any

from factory.storage.interface import SQLStore

from ..models import SessionRecord
from .sql_mutations import SessionMutationsMixin
from .sql_pinned_messages import SessionPinnedMessagesMixin
from .sql_pins import SessionPinsMixin
from .sql_steer import SessionSteerMixin
from .sql_tags import SessionTagsMixin
from .sql_rows import (
    SESSION_FIELDS, SESSION_INDEX_SCHEMA, SESSION_SCHEMA, STEER_SCHEMA,
    columns as _columns, migrate_sessions, now as _now, params, session_from,
    values as _values,
)


class SQLSessionStore(
    SessionMutationsMixin, SessionPinnedMessagesMixin, SessionPinsMixin,
    SessionSteerMixin, SessionTagsMixin,
):
    """Revision-fenced session and mailbox persistence over Storage SQLStore."""

    def __init__(self, sql: SQLStore) -> None:
        self._sql = sql
        sql.execute(SESSION_SCHEMA)
        migrate_sessions(sql)
        sql.execute(SESSION_INDEX_SCHEMA)
        sql.execute(STEER_SCHEMA)

    def create(self, record: SessionRecord) -> SessionRecord:
        self._sql.execute(
            f"INSERT INTO companion_sessions ({_columns(SESSION_FIELDS)}) "
            f"VALUES ({_values(SESSION_FIELDS)})",
            params(record),
        )
        return record

    def get(
        self, tenant_id: str, owner_id: str, session_id: str,
    ) -> SessionRecord | None:
        row = self._sql.fetch_one(
            "SELECT * FROM companion_sessions WHERE tenant_id=:tenant_id "
            "AND owner_id=:owner_id AND session_id=:session_id",
            {"tenant_id": tenant_id, "owner_id": owner_id, "session_id": session_id},
        )
        return session_from(row)

    def get_by_thread(
        self, tenant_id: str, owner_id: str, thread_id: str,
    ) -> SessionRecord | None:
        row = self._sql.fetch_one(
            "SELECT * FROM companion_sessions WHERE tenant_id=:tenant_id "
            "AND owner_id=:owner_id AND thread_id=:thread_id",
            {"tenant_id": tenant_id, "owner_id": owner_id, "thread_id": thread_id},
        )
        return session_from(row)

    def list(
        self, tenant_id: str, owner_id: str, *, include_archived: bool = False,
    ) -> list[SessionRecord]:
        archive = "" if include_archived else " AND archived_at IS NULL"
        rows = self._sql.fetch_all(
            "SELECT * FROM companion_sessions WHERE tenant_id=:tenant_id "
            f"AND owner_id=:owner_id{archive} ORDER BY "
            "CASE WHEN pinned_rank IS NULL THEN 1 ELSE 0 END,"
            "pinned_rank,updated_at DESC,session_id",
            {"tenant_id": tenant_id, "owner_id": owner_id},
        )
        return [record for row in rows if (record := session_from(row)) is not None]

    def rename(
        self, tenant_id: str, owner_id: str, session_id: str,
        title: str, expected_revision: int,
    ) -> SessionRecord | None:
        result = self._sql.execute(
            "UPDATE companion_sessions SET title=:title, updated_at=:now, "
            "revision=revision+1 WHERE tenant_id=:tenant_id AND owner_id=:owner_id "
            "AND session_id=:session_id AND revision=:expected_revision",
            self._session_args(
                tenant_id, owner_id, session_id, expected_revision,
                title=title, now=_now(),
            ),
        )
        return self.get(tenant_id, owner_id, session_id) if result.row_count == 1 else None

    def set_archived(
        self, tenant_id: str, owner_id: str, session_id: str,
        archived: bool, expected_revision: int,
    ) -> SessionRecord | None:
        now = _now()
        result = self._sql.execute(
            "UPDATE companion_sessions SET archived_at=:archived_at, "
            "pinned_rank=CASE WHEN :archived THEN NULL ELSE pinned_rank END, updated_at=:now, "
            "revision=revision+1 WHERE tenant_id=:tenant_id AND owner_id=:owner_id "
            "AND session_id=:session_id AND revision=:expected_revision",
            self._session_args(
                tenant_id, owner_id, session_id, expected_revision,
                archived_at=now if archived else None, archived=archived, now=now,
            ),
        )
        return self.get(tenant_id, owner_id, session_id) if result.row_count == 1 else None

    def delete(
        self, tenant_id: str, owner_id: str, session_id: str, expected_revision: int,
    ) -> bool:
        """Hard-delete a session (row 8, feature-map — "Older sessions" per-
        session delete). Revision-fenced like every other mutation here, so
        a stale delete is rejected instead of racing a concurrent change.
        Steer mailbox rows for this session are removed too — they have no
        meaning once the session itself is gone."""
        result = self._sql.execute(
            "DELETE FROM companion_sessions WHERE tenant_id=:tenant_id "
            "AND owner_id=:owner_id AND session_id=:session_id "
            "AND revision=:expected_revision",
            self._session_args(tenant_id, owner_id, session_id, expected_revision),
        )
        if result.row_count == 1:
            self._sql.execute(
                "DELETE FROM session_steers WHERE tenant_id=:tenant_id "
                "AND owner_id=:owner_id AND session_id=:session_id",
                {"tenant_id": tenant_id, "owner_id": owner_id, "session_id": session_id},
            )
            return True
        return False

    def count_archived(self, tenant_id: str, owner_id: str) -> int:
        """Row 8 (feature-map) bulk "Delete all" — the upstream preview
        count (``GET /api/sessions/clearable/count``) before the owner
        commits to a bulk delete."""
        row = self._sql.fetch_one(
            "SELECT COUNT(*) AS n FROM companion_sessions WHERE tenant_id=:tenant_id "
            "AND owner_id=:owner_id AND archived_at IS NOT NULL",
            {"tenant_id": tenant_id, "owner_id": owner_id},
        )
        return int(row["n"]) if row else 0

    def delete_archived(self, tenant_id: str, owner_id: str) -> int:
        """Row 8 bulk "Delete all" — clears every archived session for this
        owner (upstream ``DELETE /api/sessions``). No revision fencing: a
        blanket bulk action, not a targeted CAS mutation, matching upstream's
        own shape. Never touches an active (non-archived) session. Uses a
        correlated subquery (not dynamic placeholder generation) so no
        string-built IN-clause is ever near user-controlled values."""
        self._sql.execute(
            "DELETE FROM session_steers WHERE tenant_id=:tenant_id "
            "AND owner_id=:owner_id AND session_id IN ("
            "SELECT session_id FROM companion_sessions WHERE tenant_id=:tenant_id "
            "AND owner_id=:owner_id AND archived_at IS NOT NULL)",
            {"tenant_id": tenant_id, "owner_id": owner_id},
        )
        result = self._sql.execute(
            "DELETE FROM companion_sessions WHERE tenant_id=:tenant_id "
            "AND owner_id=:owner_id AND archived_at IS NOT NULL",
            {"tenant_id": tenant_id, "owner_id": owner_id},
        )
        return result.row_count

    @staticmethod
    def _session_args(
        tenant_id: str, owner_id: str, session_id: str,
        expected_revision: int, **extra: Any,
    ) -> dict[str, Any]:
        return {"tenant_id": tenant_id, "owner_id": owner_id,
                "session_id": session_id, "expected_revision": expected_revision, **extra}


__all__ = ["SQLSessionStore"]
