"""Identity-bound session lifecycle behavior."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import TypeAdapter, ValidationError

from .errors import (
    SendIdRejectedError, SessionConflictError, SessionIdentityError,
    SessionNotFoundError,
)
from .models import Identity, SessionRecord
from .ports import SessionStore, SteerMailbox
from .project_lifecycle import (
    ProjectLifecycleMixin, _validated_binding, _validated_model,
)
from .pinning import SessionPinningMixin
from .pinned_messages import SessionPinnedMessagesLifecycleMixin
from .steer_lifecycle import SessionSteerMixin
from .summary_lifecycle import SessionSummaryLifecycleMixin
from .tagging import SessionTaggingMixin

_IDENTITY = TypeAdapter(Identity)


class SessionLifecycle(
    SessionTaggingMixin, SessionPinningMixin, SessionPinnedMessagesLifecycleMixin,
    SessionSummaryLifecycleMixin, ProjectLifecycleMixin, SessionSteerMixin,
):
    """Business behavior over owner-scoped session and mailbox ports."""

    def __init__(self, store: SessionStore | SteerMailbox) -> None:
        self.store = store

    @staticmethod
    def identity(envelope: dict[str, Any] | None) -> tuple[str, str]:
        if not isinstance(envelope, dict):
            raise SessionIdentityError
        try:
            tenant_id = _IDENTITY.validate_python(envelope.get("tenant_id"))
            owner_id = _IDENTITY.validate_python(envelope.get("principal_id"))
        except ValidationError as exc:
            raise SessionIdentityError from exc
        return tenant_id, owner_id

    def create(
        self, tenant_id: str, owner_id: str, title: str, agent_id: str, model: str,
        mode: str = "", workspace: str = "", project: str = "", origin: str = "user",
        crew_id: str = "", memory_scope: str = "", thread_id: str | None = None,
    ) -> SessionRecord:
        now = datetime.now(timezone.utc)
        crew_id, memory_scope, agent_id = _validated_binding(
            crew_id, memory_scope, agent_id,
        )
        session_id = f"s_{uuid4().hex}"
        thread = thread_id or f"t_{uuid4().hex}"
        if project:
            from .project_lifecycle import _validated_project
            project = _validated_project(tenant_id, owner_id, session_id, project)
        return self.store.create(SessionRecord(
            tenant_id=tenant_id, owner_id=owner_id, session_id=session_id,
            thread_id=thread, title=title, agent_id=agent_id, model=model,
            mode=mode, workspace=workspace, project=project, origin=origin,
            crew_id=crew_id, memory_scope=memory_scope,
            created_at=now, updated_at=now, revision=1,
        ))

    def get(self, tenant_id: str, owner_id: str, session_id: str) -> SessionRecord:
        value = self.store.get(tenant_id, owner_id, session_id)
        if value is None:
            raise SessionNotFoundError
        return value

    def ensure_thread(
        self, tenant_id: str, owner_id: str, thread_id: str,
        title: str, agent_id: str, model: str,
        crew_id: str = "", memory_scope: str = "", mode: str = "",
        project: str = "",
    ) -> SessionRecord:
        existing = self.store.get_by_thread(tenant_id, owner_id, thread_id)
        if existing is not None:
            return existing
        try:
            return self.create(
                tenant_id, owner_id, title, agent_id, model, mode=mode,
                crew_id=crew_id, memory_scope=memory_scope, project=project,
                origin="chat", thread_id=thread_id,
            )
        except Exception:
            existing = self.store.get_by_thread(tenant_id, owner_id, thread_id)
            if existing is None:
                raise
            return existing

    def resolve_thread(
        self, tenant_id: str, owner_id: str, thread_id: str,
    ) -> SessionRecord:
        value = self.store.get_by_thread(tenant_id, owner_id, thread_id)
        if value is None:
            raise SessionNotFoundError
        return value

    def list(
        self, tenant_id: str, owner_id: str, include_archived: bool = False,
    ) -> list[SessionRecord]:
        return self.store.list(tenant_id, owner_id, include_archived=include_archived)

    def rename(
        self, tenant_id: str, owner_id: str, session_id: str,
        title: str, expected_revision: int,
    ) -> SessionRecord:
        value = self.store.rename(
            tenant_id, owner_id, session_id, title, expected_revision,
        )
        return self._session_result(value, tenant_id, owner_id, session_id)

    def set_archived(
        self, tenant_id: str, owner_id: str, session_id: str,
        archived: bool, expected_revision: int,
    ) -> SessionRecord:
        value = self.store.set_archived(
            tenant_id, owner_id, session_id, archived, expected_revision,
        )
        return self._session_result(value, tenant_id, owner_id, session_id)

    def set_active_checkpoint(
        self, tenant_id: str, owner_id: str, session_id: str,
        checkpoint_id: str | None, expected_revision: int,
    ) -> SessionRecord:
        """Row 16 (feature-map) — pin the checkpoint branch a regenerate
        or variant switch made "current" for this thread, so an ordinary
        next turn's implicit resumption stays deterministic once sibling
        branches exist (see ``SessionRecord.active_checkpoint_id``)."""
        value = self.store.set_active_checkpoint(
            tenant_id, owner_id, session_id, checkpoint_id, expected_revision,
        )
        return self._session_result(value, tenant_id, owner_id, session_id)

    def delete(
        self, tenant_id: str, owner_id: str, session_id: str, expected_revision: int,
    ) -> bool:
        """Hard-delete a session (row 8, feature-map). Fails closed the
        same way every other mutation does: a session that doesn't exist
        (already deleted, foreign owner) or a stale revision both raise
        ``SessionConflictError`` via the not-found check below, never a
        silent no-op false."""
        deleted = self.store.delete(tenant_id, owner_id, session_id, expected_revision)
        if deleted:
            return True
        self.get(tenant_id, owner_id, session_id)
        raise SessionConflictError

    def count_archived(self, tenant_id: str, owner_id: str) -> int:
        """Row 8 bulk "Delete all" preview count."""
        return self.store.count_archived(tenant_id, owner_id)

    def delete_archived(self, tenant_id: str, owner_id: str) -> int:
        """Row 8 bulk "Delete all" — clears every archived session for this
        owner. No revision fencing (matches upstream's own blanket-delete
        shape); returns the number actually removed."""
        return self.store.delete_archived(tenant_id, owner_id)

    def fork(
        self, tenant_id: str, owner_id: str, session_id: str,
    ) -> SessionRecord:
        """Row 14 — branch a new session from an existing one's transcript.

        Upstream's exact contract: "an incognito or temporary session
        forks into a child of the SAME memory mode" — the child never
        changes mode, crew, memory scope, agent, model, or project; only
        the thread/session identity is new. The transcript copy itself
        (the LangGraph checkpoint history) is the caller's job — this
        brick owns session identity, not chat transcripts — mirroring how
        ``ensure_thread`` never touches a checkpoint either."""
        source = self.get(tenant_id, owner_id, session_id)
        title = f"{source.title} (fork)" if len(source.title) <= 190 else source.title
        return self.create(
            tenant_id, owner_id, title, source.agent_id, source.model,
            mode=source.mode, workspace=source.workspace, project=source.project,
            origin=source.origin, crew_id=source.crew_id,
            memory_scope=source.memory_scope,
        )

    def _session_result(
        self, value: SessionRecord | None, tenant_id: str,
        owner_id: str, session_id: str,
    ) -> SessionRecord:
        if value is not None:
            return value
        self.get(tenant_id, owner_id, session_id)
        raise SessionConflictError


__all__ = [
    "SendIdRejectedError", "SessionConflictError", "SessionIdentityError",
    "SessionLifecycle", "SessionNotFoundError",
]
