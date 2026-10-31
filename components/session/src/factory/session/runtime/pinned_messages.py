"""Session pinned-message lifecycle behavior (row 9, feature-map)."""
from __future__ import annotations

from typing import Any

from .models import SessionRecord


class SessionPinnedMessagesLifecycleMixin:
    store: Any

    def set_pinned_messages(
        self, tenant_id: str, owner_id: str, session_id: str,
        pinned_message_ids: tuple[str, ...], expected_revision: int,
    ) -> SessionRecord:
        value = self.store.set_pinned_messages(
            tenant_id, owner_id, session_id, pinned_message_ids, expected_revision,
        )
        return self._session_result(value, tenant_id, owner_id, session_id)


__all__ = ["SessionPinnedMessagesLifecycleMixin"]
