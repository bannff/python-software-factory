"""Revision-fenced durable Session tag persistence."""
from __future__ import annotations

from typing import Any

from ..models import SessionRecord
from .sql_rows import now


class SessionTagsMixin:
    _sql: Any

    def set_tags(
        self, tenant_id: str, owner_id: str, session_id: str,
        tags: tuple[str, ...], expected_revision: int,
    ) -> SessionRecord | None:
        current = self.get(tenant_id, owner_id, session_id)
        if current is None or current.archived_at or current.revision != expected_revision:
            return None
        if current.tags == tags:
            return current
        result = self._sql.execute(
            "UPDATE companion_sessions SET tags=:tags,updated_at=:now,"
            "revision=revision+1 WHERE tenant_id=:tenant_id AND owner_id=:owner_id "
            "AND session_id=:session_id AND revision=:revision AND archived_at IS NULL",
            {"tenant_id": tenant_id, "owner_id": owner_id, "session_id": session_id,
             "tags": ",".join(tags), "now": now(), "revision": expected_revision},
        )
        return self.get(tenant_id, owner_id, session_id) if result.row_count == 1 else None


__all__ = ["SessionTagsMixin"]
