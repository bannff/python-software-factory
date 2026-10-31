"""Session-owned background completion delivery lifecycle."""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any, Protocol

from factory.mcp_utils.interface import protected_canonical_json

from .errors import SessionConflictError, SessionNotFoundError
from .models import (
    CompletionDelivery, CompletionOutcome, CompletionState, SessionRecord,
)


class CompletionStore(Protocol):
    def append(self, delivery: CompletionDelivery) -> CompletionDelivery: ...
    def get(self, tenant_id: str, owner_id: str, session_id: str,
            run_id: str) -> CompletionDelivery | None: ...
    def list_pending(self, tenant_id: str, owner_id: str,
                     session_id: str) -> list[CompletionDelivery]: ...
    def has_pending(self, tenant_id: str, owner_id: str, session_id: str) -> bool: ...
    def mark_delivered(self, tenant_id: str, owner_id: str, session_id: str,
                       run_id: str, result_digest: str, revision: int,
                       delivered_at: str) -> CompletionDelivery | None: ...


class CompletionLifecycle:
    def __init__(self, store: CompletionStore, sessions: Any) -> None:
        self.store, self.sessions = store, sessions

    @staticmethod
    def digest(outcome: str, summary: str) -> str:
        value = protected_canonical_json({"outcome": outcome, "summary": summary})
        return hashlib.sha256(value).hexdigest()

    def record(
        self, tenant_id: str, owner_id: str, session_id: str, run_id: str,
        outcome: str, summary: str, result_digest: str, revision: int,
    ) -> CompletionDelivery:
        if revision != 1 or self.digest(outcome, summary) != result_digest:
            raise SessionConflictError
        self._session(tenant_id, owner_id, session_id)
        try:
            return self.store.append(CompletionDelivery(
                tenant_id=tenant_id, owner_id=owner_id, session_id=session_id,
                run_id=run_id, outcome=CompletionOutcome(outcome), summary=summary,
                result_digest=result_digest, state=CompletionState.PENDING,
                created_at=datetime.now(timezone.utc), revision=1,
            ))
        except ValueError as exc:
            raise SessionConflictError from exc

    def pending(
        self, tenant_id: str, owner_id: str, session_id: str,
    ) -> list[CompletionDelivery]:
        self._session(tenant_id, owner_id, session_id)
        return self.store.list_pending(tenant_id, owner_id, session_id)

    def has_pending(self, tenant_id: str, owner_id: str, session_id: str) -> bool:
        return self.store.has_pending(tenant_id, owner_id, session_id)

    def acknowledge(
        self, tenant_id: str, owner_id: str, session_id: str, run_id: str,
        result_digest: str, revision: int,
    ) -> CompletionDelivery:
        self._session(tenant_id, owner_id, session_id)
        value = self.store.mark_delivered(
            tenant_id, owner_id, session_id, run_id, result_digest, revision,
            datetime.now(timezone.utc).isoformat(),
        )
        if value is not None:
            return value
        existing = self.store.get(tenant_id, owner_id, session_id, run_id)
        if existing is None:
            raise SessionNotFoundError
        raise SessionConflictError

    def _session(self, tenant_id: str, owner_id: str, session_id: str) -> SessionRecord:
        value = self.sessions.get(tenant_id, owner_id, session_id)
        if value is None:
            raise SessionNotFoundError
        return value


__all__ = ["CompletionLifecycle", "CompletionStore"]
