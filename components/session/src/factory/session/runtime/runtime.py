"""Runtime composition for the session capability."""
from __future__ import annotations

import os
from typing import Any

from factory.storage.interface import get_sql_store

from .adapters.completion_sql import SQLCompletionStore
from .adapters.sql import SQLSessionStore
from .completion import CompletionLifecycle
from .lifecycle import SessionLifecycle
from .models import SessionRecord


class SessionRuntime:
    """Session capability runtime with lazy durable local composition."""

    def __init__(
        self, lifecycle: SessionLifecycle | None = None,
        completion: CompletionLifecycle | None = None,
    ) -> None:
        self._lifecycle = lifecycle
        self._completion = completion

    @property
    def lifecycle(self) -> SessionLifecycle:
        if self._lifecycle is None:
            db_path = os.getenv(
                "COMPANION_X_SESSION_DB_PATH", "./.storage/sessions.db",
            )
            store = SQLSessionStore(get_sql_store("sqlite", db_path=db_path))
            store.reconcile_written()
            self._lifecycle = SessionLifecycle(store)
        return self._lifecycle

    @property
    def completion(self) -> CompletionLifecycle:
        if self._completion is None:
            db_path = os.getenv(
                "COMPANION_X_SESSION_DB_PATH", "./.storage/sessions.db",
            )
            sql = get_sql_store("sqlite", db_path=db_path)
            self._completion = CompletionLifecycle(
                SQLCompletionStore(sql), self.lifecycle.store,
            )
        return self._completion

    def get_session(
        self, tenant_id: str, owner_id: str, session_id: str,
    ) -> SessionRecord:
        session = self.lifecycle.get(tenant_id, owner_id, session_id)
        return session.model_copy(update={
            "unread": self.completion.has_pending(tenant_id, owner_id, session_id),
        })

    def list_sessions(
        self, tenant_id: str, owner_id: str, include_archived: bool = False,
    ) -> list[SessionRecord]:
        sessions = self.lifecycle.list(tenant_id, owner_id, include_archived)
        return [session.model_copy(update={
            "unread": self.completion.has_pending(
                tenant_id, owner_id, session.session_id,
            ),
        }) for session in sessions]

    @staticmethod
    def get_capabilities() -> dict[str, Any]:
        return {
            "name": "session", "version": "1.0.0",
            "features": [
                "session_registry", "tenant_owned_sessions",
                "steer_delivery_state", "completion_delivery",
                "revision_fenced_cas",
            ],
        }

    @staticmethod
    def health_check() -> dict[str, Any]:
        return {"healthy": True, "backend": "sqlite"}

    @staticmethod
    def describe_config_schema() -> dict[str, Any]:
        return {
            "type": "object", "additionalProperties": False,
            "properties": {
                "backend": {"type": "string", "enum": ["sqlite"]},
                "database_path": {"type": "string"},
            },
        }


_runtime: SessionRuntime | None = None


def get_runtime() -> SessionRuntime:
    global _runtime
    if _runtime is None:
        _runtime = SessionRuntime()
    return _runtime


__all__ = ["SessionRuntime", "get_runtime"]
