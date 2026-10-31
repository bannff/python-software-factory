"""Steer-mailbox mixin for ``SessionLifecycle``.

Split out of ``lifecycle.py`` to keep that file under the 200 LOC ceiling —
same split rationale already applied at the MCP layer (``steering.py``) and
SQL adapter layer (``sql_steer.py``) this cycle: steer delivery is a
genuinely separate concern from session lifecycle mutations.
"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from .errors import SendIdRejectedError, SessionConflictError, SessionNotFoundError
from .models import SessionRecord, SteerMessage, SteerState
from .send_ids import credential_clean_send_id


class SessionSteerMixin:
    """Requires ``self.store``, ``self.get()`` from the composing class."""

    def steer(
        self, tenant_id: str, owner_id: str, session_id: str,
        send_id: str, content: str,
    ) -> SteerMessage:
        if not credential_clean_send_id(send_id):
            raise SendIdRejectedError
        self._require_active(tenant_id, owner_id, session_id)
        try:
            return self.store.append(SteerMessage(
                tenant_id=tenant_id, owner_id=owner_id, session_id=session_id,
                delivery_id=f"d_{uuid4().hex}", send_id=send_id, content=content,
                state=SteerState.WRITTEN, created_at=datetime.now(timezone.utc), revision=1,
            ))
        except ValueError as exc:
            raise SessionNotFoundError from exc

    def get_steer(
        self, tenant_id: str, owner_id: str, session_id: str, delivery_id: str,
    ) -> SteerMessage:
        value = self.store.get_steer(tenant_id, owner_id, session_id, delivery_id)
        if value is None:
            raise SessionNotFoundError
        return value

    def list_written(
        self, tenant_id: str, owner_id: str, session_id: str,
    ) -> list[SteerMessage]:
        self._require_active(tenant_id, owner_id, session_id)
        return self.store.list_written(tenant_id, owner_id, session_id)

    def acknowledge(
        self, tenant_id: str, owner_id: str, session_id: str,
        delivery_id: str, revision: int,
    ) -> SteerMessage:
        return self._settle(
            tenant_id, owner_id, session_id, delivery_id,
            revision, SteerState.CONSUMED,
        )

    def requeue(
        self, tenant_id: str, owner_id: str, session_id: str,
        delivery_id: str, revision: int,
    ) -> SteerMessage:
        return self._settle(
            tenant_id, owner_id, session_id, delivery_id,
            revision, SteerState.REQUEUED,
        )

    def _settle(
        self, tenant_id: str, owner_id: str, session_id: str,
        delivery_id: str, revision: int, state: SteerState,
    ) -> SteerMessage:
        self._require_active(tenant_id, owner_id, session_id)
        value = self.store.transition(
            tenant_id, owner_id, session_id, delivery_id, state, revision,
        )
        if value is not None:
            return value
        try:
            self.get_steer(tenant_id, owner_id, session_id, delivery_id)
        except SessionNotFoundError:
            raise
        raise SessionConflictError

    def _require_active(
        self, tenant_id: str, owner_id: str, session_id: str,
    ) -> SessionRecord:
        value = self.get(tenant_id, owner_id, session_id)
        if value.archived_at is not None:
            raise SessionNotFoundError
        return value


__all__ = ["SessionSteerMixin"]
