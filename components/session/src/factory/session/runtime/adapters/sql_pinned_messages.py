"""Revision-fenced durable Session pinned-message persistence."""
from __future__ import annotations

import json
from typing import Any

from ..models import SessionRecord
from .sql_rows import now


class SessionPinnedMessagesMixin:
    _sql: Any

    def set_pinned_messages(
        self, tenant_id: str, owner_id: str, session_id: str,
        pinned_message_ids: tuple[str, ...], expected_revision: int,
    ) -> SessionRecord | None:
        current = self.get(tenant_id, owner_id, session_id)
        if current is None or current.archived_at or current.revision != expected_revision:
            return None
        if current.pinned_message_ids == pinned_message_ids:
            return current
        result = self._sql.execute(
            "UPDATE companion_sessions SET pinned_message_ids=:pins,updated_at=:now,"
            "revision=revision+1 WHERE tenant_id=:tenant_id AND owner_id=:owner_id "
            "AND session_id=:session_id AND revision=:revision AND archived_at IS NULL",
            {"tenant_id": tenant_id, "owner_id": owner_id, "session_id": session_id,
             "pins": json.dumps(list(pinned_message_ids)), "now": now(),
             "revision": expected_revision},
        )
        return self.get(tenant_id, owner_id, session_id) if result.row_count == 1 else None


__all__ = ["SessionPinnedMessagesMixin"]
