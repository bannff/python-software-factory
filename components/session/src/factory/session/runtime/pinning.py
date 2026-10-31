"""Session pin lifecycle behavior over the canonical persistence port."""
from __future__ import annotations

from typing import Any

from .models import SessionRecord


class SessionPinningMixin:
    store: Any

    def set_pinned(
        self, tenant_id: str, owner_id: str, session_id: str,
        pinned: bool, expected_revision: int,
    ) -> SessionRecord:
        value = self.store.set_pinned(
            tenant_id, owner_id, session_id, pinned, expected_revision,
        )
        return self._session_result(value, tenant_id, owner_id, session_id)

    def move_pinned(
        self, tenant_id: str, owner_id: str, session_id: str,
        before_session_id: str | None, expected_revision: int,
    ) -> SessionRecord:
        value = self.store.move_pinned(
            tenant_id, owner_id, session_id, before_session_id, expected_revision,
        )
        return self._session_result(value, tenant_id, owner_id, session_id)


__all__ = ["SessionPinningMixin"]
