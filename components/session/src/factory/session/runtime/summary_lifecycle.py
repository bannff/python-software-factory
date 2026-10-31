"""Session rolling-summary (row 18) and folder-filing (row 6) lifecycle
behavior. Both are simple single-column CAS writes kept out of the
already near-ceiling ``lifecycle.py`` (same split reason as
``pinned_messages.py``).
"""
from __future__ import annotations

from typing import Any

from .models import SessionRecord


class SessionSummaryLifecycleMixin:
    store: Any

    def set_summary(
        self, tenant_id: str, owner_id: str, session_id: str,
        summary: str, expected_revision: int,
    ) -> SessionRecord:
        """Row 18 — apply the session's rolling conversation summary through
        the same revision-fenced write every other mutation uses."""
        value = self.store.set_summary(
            tenant_id, owner_id, session_id, summary, expected_revision,
        )
        return self._session_result(value, tenant_id, owner_id, session_id)

    def set_folder(
        self, tenant_id: str, owner_id: str, session_id: str,
        folder: str, expected_revision: int,
    ) -> SessionRecord:
        """Row 6 — file the session under a folder name through the same
        revision-fenced write every other mutation uses."""
        value = self.store.set_folder(
            tenant_id, owner_id, session_id, folder, expected_revision,
        )
        return self._session_result(value, tenant_id, owner_id, session_id)


__all__ = ["SessionSummaryLifecycleMixin"]
