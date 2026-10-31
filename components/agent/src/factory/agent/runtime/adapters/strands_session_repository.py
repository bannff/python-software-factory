"""SQL-backed strands ``SessionRepository`` (phase 2, issue #89).

Implements the strands 1.56 ``SessionRepository`` ABC over the storage
brick's public ``SQLStore`` port (the ``SqlInboxStore`` pattern: named
``:params``, ``ON CONFLICT DO NOTHING``). Backend is selected through
``get_sql_store`` so a postgres deployment swaps in via the same
factory — sqlite remains the default. The DB file is ALWAYS separate
from the LangGraph ``AsyncSqliteSaver`` checkpoints file (that saver
runs WAL + ``setup()`` on connect; sharing it means lock contention).

Durable history only: live interrupts are serialized inside agent
internal state like strands' own file manager does — ``fork_session``
copies the durable rows, never an in-flight interrupt.
"""
from __future__ import annotations

import os
from typing import Any

from factory.config.interface import get_infra
from factory.storage.interface import SQLStore, get_sql_store

from strands.session.session_repository import SessionRepository
from strands.types.session import (
    Session, SessionAgent, SessionMessage, SessionType,
)

from .strands_session_sql import (
    AGENT_DDL, AGENT_INSERT, AGENT_UPDATE, MESSAGE_DDL, MESSAGE_INSERT,
    MESSAGE_UPDATE, SESSION_DDL, SESSION_INSERT, agent_from_row, agent_params,
    message_from_row, message_params,
)

_INFRA_BACKEND_KEY = "storage.sql.backend"
_DEFAULT_DB_PATH = "./.storage/strands-sessions.db"
_DB_PATH_ENV = "COMPANION_X_STRANDS_SESSIONS_DB_PATH"


class SqlSessionRepository(SessionRepository):
    """``SessionRepository`` over ``factory.storage`` SQLStore (sqlite default)."""

    def __init__(self, sql: SQLStore | None = None, *, db_path: str | None = None) -> None:
        if sql is None:
            backend = str(get_infra(_INFRA_BACKEND_KEY, "sqlite") or "sqlite")
            path = db_path or os.getenv(_DB_PATH_ENV, _DEFAULT_DB_PATH)
            sql = get_sql_store(backend, db_path=path)
        self._sql = sql
        self.initialize()

    def initialize(self) -> None:
        self._sql.execute(SESSION_DDL)
        self._sql.execute(AGENT_DDL)
        self._sql.execute(MESSAGE_DDL)

    # -- session ---------------------------------------------------------

    def create_session(self, session: Session, **kwargs: Any) -> Session:
        self._sql.execute(SESSION_INSERT, {
            "session_id": session.session_id,
            "session_type": _type_value(session.session_type),
            "created_at": session.created_at, "updated_at": session.updated_at,
        })
        return session

    def read_session(self, session_id: str, **kwargs: Any) -> Session | None:
        row = self._sql.fetch_one(
            "SELECT session_id, session_type, created_at, updated_at"
            " FROM strands_sessions WHERE session_id = :sid",
            {"sid": session_id},
        )
        if row is None:
            return None
        # Re-type the stored enum string before Session.from_dict.
        row = {**row, "session_type": SessionType(row["session_type"])}
        return Session.from_dict(row)

    # -- agent -----------------------------------------------------------

    def create_agent(self, session_id: str, session_agent: SessionAgent, **kwargs: Any) -> None:
        self._sql.execute(AGENT_INSERT, agent_params(session_id, session_agent))

    def read_agent(self, session_id: str, agent_id: str, **kwargs: Any) -> SessionAgent | None:
        row = self._sql.fetch_one(
            "SELECT agent_id, state, conversation_manager_state, _internal_state,"
            " created_at, updated_at FROM strands_session_agents"
            " WHERE session_id = :sid AND agent_id = :aid",
            {"sid": session_id, "aid": agent_id},
        )
        return agent_from_row(row) if row else None

    def update_agent(self, session_id: str, session_agent: SessionAgent, **kwargs: Any) -> None:
        self._sql.execute(AGENT_UPDATE, agent_params(session_id, session_agent))

    # -- message ---------------------------------------------------------

    def create_message(
        self, session_id: str, agent_id: str, session_message: SessionMessage, **kwargs: Any,
    ) -> None:
        self._sql.execute(MESSAGE_INSERT, message_params(session_id, agent_id, session_message))

    def read_message(
        self, session_id: str, agent_id: str, message_id: int, **kwargs: Any,
    ) -> SessionMessage | None:
        row = self._sql.fetch_one(
            "SELECT message_id, message, redact_message, created_at, updated_at"
            " FROM strands_session_messages WHERE session_id = :sid"
            " AND agent_id = :aid AND message_id = :mid",
            {"sid": session_id, "aid": agent_id, "mid": message_id},
        )
        return message_from_row(row) if row else None

    def update_message(
        self, session_id: str, agent_id: str, session_message: SessionMessage, **kwargs: Any,
    ) -> None:
        self._sql.execute(MESSAGE_UPDATE, message_params(session_id, agent_id, session_message))

    def list_messages(
        self, session_id: str, agent_id: str, limit: int | None = None, offset: int = 0,
        **kwargs: Any,
    ) -> list[SessionMessage]:
        q = (
            "SELECT message_id, message, redact_message, created_at, updated_at"
            " FROM strands_session_messages WHERE session_id = :sid"
            " AND agent_id = :aid ORDER BY message_id ASC LIMIT :lim OFFSET :off"
        )
        rows = self._sql.fetch_all(q, {
            "sid": session_id, "aid": agent_id,
            "lim": -1 if limit is None else limit, "off": offset,
        })
        return [message_from_row(row) for row in rows]

    # -- fork / delete / listing ------------------------------------------

    def fork_session(self, source_id: str, target_id: str) -> bool:
        """Copy session+agents+messages rows to ``target_id``.

        False when the source session has no agents yet (an empty session
        forks into an equally empty one — a no-op, not an error, matching
        ``langchain_checkpoints.copy_thread`` semantics). The target is
        independent after the fork: rows are plain copies, no shared keys.
        """
        if self._sql.fetch_one(
            "SELECT agent_id FROM strands_session_agents WHERE session_id = :sid LIMIT 1",
            {"sid": source_id},
        ) is None:
            return False
        self._sql.execute(
            "INSERT OR IGNORE INTO strands_sessions"
            " (session_id, session_type, created_at, updated_at)"
            " SELECT :target, session_type, created_at, updated_at"
            " FROM strands_sessions WHERE session_id = :source",
            {"target": target_id, "source": source_id},
        )
        self._sql.execute(
            "INSERT OR IGNORE INTO strands_session_agents"
            " (session_id, agent_id, state, conversation_manager_state,"
            "  _internal_state, created_at, updated_at)"
            " SELECT :target, agent_id, state, conversation_manager_state,"
            "  _internal_state, created_at, updated_at"
            " FROM strands_session_agents WHERE session_id = :source",
            {"target": target_id, "source": source_id},
        )
        self._sql.execute(
            "INSERT OR IGNORE INTO strands_session_messages"
            " (session_id, agent_id, message_id, message, redact_message,"
            "  created_at, updated_at)"
            " SELECT :target, agent_id, message_id, message, redact_message,"
            "  created_at, updated_at"
            " FROM strands_session_messages WHERE session_id = :source",
            {"target": target_id, "source": source_id},
        )
        return True

    def delete_session(self, session_id: str) -> None:
        """Durable delete of one session's rows (``close`` path)."""
        for table in ("strands_session_messages", "strands_session_agents", "strands_sessions"):
            self._sql.execute(f"DELETE FROM {table} WHERE session_id = :sid", {"sid": session_id})

    def session_ids(self) -> tuple[str, ...]:
        """All stored session ids (thread close scans persona keys)."""
        rows = self._sql.fetch_all("SELECT session_id FROM strands_sessions")
        return tuple(str(row["session_id"]) for row in rows)

    def agent_ids_for(self, session_id: str) -> tuple[str, ...]:
        """Stored agent (persona) ids inside one session."""
        rows = self._sql.fetch_all(
            "SELECT agent_id FROM strands_session_agents WHERE session_id = :sid"
            " ORDER BY created_at ASC",
            {"sid": session_id},
        )
        return tuple(str(row["agent_id"]) for row in rows)


def _type_value(session_type: SessionType | str) -> str:
    return session_type.value if isinstance(session_type, SessionType) else str(session_type)


__all__ = ["SqlSessionRepository"]
