"""Session tag lifecycle behavior."""
from __future__ import annotations

from typing import Any

from .models import SessionRecord


class SessionTaggingMixin:
    store: Any

    def set_tags(
        self, tenant_id: str, owner_id: str, session_id: str,
        tags: tuple[str, ...], expected_revision: int,
    ) -> SessionRecord:
        value = self.store.set_tags(
            tenant_id, owner_id, session_id, tags, expected_revision,
        )
        return self._session_result(value, tenant_id, owner_id, session_id)


__all__ = ["SessionTaggingMixin"]
