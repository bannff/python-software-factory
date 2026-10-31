"""Revision-fenced, owner-scoped binding mutations for the SQL session store."""
from __future__ import annotations

from typing import Any, Callable

from ..models import SessionRecord
from .sql_rows import now as _now

# Only these fixed, internal column names may be assigned by _cas_set. They are
# never derived from caller input, so the assignment fragment is injection-safe.
_ALLOWED = frozenset({
    "project", "workspace", "model", "crew_id", "memory_scope", "agent_id",
    "active_checkpoint_id", "summary", "folder",
})


class SessionMutationsMixin:
    """Column CAS updates shared by project binding, model, and crew rebind."""

    _sql: Any
    get: Callable[..., SessionRecord | None]

    def set_project(
        self, tenant_id: str, owner_id: str, session_id: str,
        project: str, expected_revision: int,
    ) -> SessionRecord | None:
        return self._cas_set(
            tenant_id, owner_id, session_id, expected_revision, project=project,
        )

    def set_model(
        self, tenant_id: str, owner_id: str, session_id: str,
        model: str, expected_revision: int,
    ) -> SessionRecord | None:
        return self._cas_set(
            tenant_id, owner_id, session_id, expected_revision, model=model,
        )

    def rebind(
        self, tenant_id: str, owner_id: str, session_id: str,
        crew_id: str, memory_scope: str, agent_id: str, model: str,
        project: str, workspace: str, expected_revision: int,
    ) -> SessionRecord | None:
        return self._cas_set(
            tenant_id, owner_id, session_id, expected_revision,
            crew_id=crew_id, memory_scope=memory_scope,
            agent_id=agent_id, model=model, project=project, workspace=workspace,
        )

    def set_summary(
        self, tenant_id: str, owner_id: str, session_id: str,
        summary: str, expected_revision: int,
    ) -> SessionRecord | None:
        """Row 18 (feature-map) — store the session's rolling conversation
        summary, revision-fenced like every other binding write here."""
        return self._cas_set(
            tenant_id, owner_id, session_id, expected_revision, summary=summary,
        )

    def set_folder(
        self, tenant_id: str, owner_id: str, session_id: str,
        folder: str, expected_revision: int,
    ) -> SessionRecord | None:
        """Row 6 (feature-map) — file the session under a folder name
        ("" = unfiled), revision-fenced like every other binding write."""
        return self._cas_set(
            tenant_id, owner_id, session_id, expected_revision, folder=folder,
        )

    def set_active_checkpoint(
        self, tenant_id: str, owner_id: str, session_id: str,
        checkpoint_id: str | None, expected_revision: int,
    ) -> SessionRecord | None:
        """Row 16 (feature-map) — pin which checkpoint branch is "current"
        for this thread. ``None`` clears the pointer (an ordinary turn
        resumes from LangGraph's own latest checkpoint again)."""
        return self._cas_set(
            tenant_id, owner_id, session_id, expected_revision,
            active_checkpoint_id=checkpoint_id,
        )

    def _cas_set(
        self, tenant_id: str, owner_id: str, session_id: str,
        expected_revision: int, **fields: str | None,
    ) -> SessionRecord | None:
        if not fields or not set(fields) <= _ALLOWED:
            raise ValueError("unsupported binding column")
        assignments = ", ".join(f"{name}=:{name}" for name in fields)
        result = self._sql.execute(
            f"UPDATE companion_sessions SET {assignments}, updated_at=:now, "
            "revision=revision+1 WHERE tenant_id=:tenant_id AND owner_id=:owner_id "
            "AND session_id=:session_id AND revision=:expected_revision "
            "AND archived_at IS NULL",
            {"tenant_id": tenant_id, "owner_id": owner_id, "session_id": session_id,
             "expected_revision": expected_revision, "now": _now(), **fields},
        )
        if result.row_count != 1:
            return None
        return self.get(tenant_id, owner_id, session_id)


__all__ = ["SessionMutationsMixin"]
