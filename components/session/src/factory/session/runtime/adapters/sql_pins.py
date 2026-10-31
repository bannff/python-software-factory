"""Durable owner-scoped Session pin membership and sparse ordering."""
from __future__ import annotations

from typing import Any

from ..models import SessionRecord
from .sql_rows import now

_GAP = 1024.0


class SessionPinsMixin:
    _sql: Any

    def set_pinned(
        self, tenant_id: str, owner_id: str, session_id: str,
        pinned: bool, expected_revision: int,
    ) -> SessionRecord | None:
        current = self.get(tenant_id, owner_id, session_id)
        if current is None or current.revision != expected_revision or current.archived_at:
            return None
        if (current.pinned_rank is not None) == pinned:
            return current
        rank = None
        if pinned:
            row = self._sql.fetch_one(
                "SELECT MAX(pinned_rank) AS rank FROM companion_sessions "
                "WHERE tenant_id=:tenant_id AND owner_id=:owner_id",
                {"tenant_id": tenant_id, "owner_id": owner_id},
            )
            rank = float(row["rank"] or 0.0) + _GAP
        return self._set_pin_rank(
            tenant_id, owner_id, session_id, rank, expected_revision,
        )

    def move_pinned(
        self, tenant_id: str, owner_id: str, session_id: str,
        before_session_id: str | None, expected_revision: int,
    ) -> SessionRecord | None:
        current = self.get(tenant_id, owner_id, session_id)
        if current is None or current.revision != expected_revision \
                or current.archived_at or current.pinned_rank is None:
            return None
        if before_session_id == session_id:
            return current
        rows = self._sql.fetch_all(
            "SELECT session_id,pinned_rank FROM companion_sessions "
            "WHERE tenant_id=:tenant_id AND owner_id=:owner_id "
            "AND archived_at IS NULL AND pinned_rank IS NOT NULL "
            "AND session_id<>:session_id ORDER BY pinned_rank,updated_at DESC,session_id",
            {"tenant_id": tenant_id, "owner_id": owner_id, "session_id": session_id},
        )
        if before_session_id is None:
            rank = float(rows[-1]["pinned_rank"]) + _GAP if rows else _GAP
        else:
            index = next((i for i, row in enumerate(rows)
                          if row["session_id"] == before_session_id), -1)
            if index < 0:
                return None
            target = float(rows[index]["pinned_rank"])
            rank = target - _GAP if index == 0 else (
                float(rows[index - 1]["pinned_rank"]) + target
            ) / 2.0
        if rank == current.pinned_rank:
            return current
        return self._set_pin_rank(
            tenant_id, owner_id, session_id, rank, expected_revision,
        )

    def _set_pin_rank(
        self, tenant_id: str, owner_id: str, session_id: str,
        rank: float | None, expected_revision: int,
    ) -> SessionRecord | None:
        result = self._sql.execute(
            "UPDATE companion_sessions SET pinned_rank=:rank,updated_at=:now,"
            "revision=revision+1 WHERE tenant_id=:tenant_id AND owner_id=:owner_id "
            "AND session_id=:session_id AND revision=:revision AND archived_at IS NULL",
            {"tenant_id": tenant_id, "owner_id": owner_id, "session_id": session_id,
             "rank": rank, "now": now(), "revision": expected_revision},
        )
        return self.get(tenant_id, owner_id, session_id) if result.row_count == 1 else None


__all__ = ["SessionPinsMixin"]
