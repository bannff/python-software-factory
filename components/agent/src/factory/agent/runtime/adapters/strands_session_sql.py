"""SQL DDL/DML and row mappers for the strands session repository.

Kept separate so ``strands_session_repository.py`` stays under the LOC
tenet; follows the ``SqlInboxStore`` conventions (named ``:params``,
``ON CONFLICT DO NOTHING``). Payload columns are JSON TEXT — strands
``Session*`` dataclasses serialize via ``to_dict``/``from_dict``.
"""
from __future__ import annotations

import json
from typing import Any

from strands.types.session import SessionAgent, SessionMessage

SESSION_DDL = """CREATE TABLE IF NOT EXISTS strands_sessions (
    session_id TEXT PRIMARY KEY, session_type TEXT NOT NULL,
    created_at TEXT NOT NULL, updated_at TEXT NOT NULL)"""

AGENT_DDL = """CREATE TABLE IF NOT EXISTS strands_session_agents (
    session_id TEXT NOT NULL, agent_id TEXT NOT NULL,
    state TEXT NOT NULL DEFAULT '{}', conversation_manager_state TEXT NOT NULL DEFAULT '{}',
    _internal_state TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
    PRIMARY KEY (session_id, agent_id))"""

MESSAGE_DDL = """CREATE TABLE IF NOT EXISTS strands_session_messages (
    session_id TEXT NOT NULL, agent_id TEXT NOT NULL, message_id INTEGER NOT NULL,
    message TEXT NOT NULL, redact_message TEXT,
    created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
    PRIMARY KEY (session_id, agent_id, message_id))"""

SESSION_INSERT = """INSERT INTO strands_sessions
    (session_id, session_type, created_at, updated_at)
    VALUES (:session_id, :session_type, :created_at, :updated_at)
    ON CONFLICT (session_id) DO NOTHING"""

AGENT_INSERT = """INSERT INTO strands_session_agents
    (session_id, agent_id, state, conversation_manager_state, _internal_state,
     created_at, updated_at)
    VALUES (:session_id, :agent_id, :state, :conversation_manager_state,
     :_internal_state, :created_at, :updated_at)
    ON CONFLICT (session_id, agent_id) DO NOTHING"""

AGENT_UPDATE = """UPDATE strands_session_agents SET
    state = :state, conversation_manager_state = :conversation_manager_state,
    _internal_state = :_internal_state, updated_at = :updated_at
    WHERE session_id = :session_id AND agent_id = :agent_id"""

MESSAGE_INSERT = """INSERT INTO strands_session_messages
    (session_id, agent_id, message_id, message, redact_message, created_at, updated_at)
    VALUES (:session_id, :agent_id, :message_id, :message, :redact_message,
     :created_at, :updated_at)
    ON CONFLICT (session_id, agent_id, message_id) DO NOTHING"""

MESSAGE_UPDATE = """UPDATE strands_session_messages SET
    message = :message, redact_message = :redact_message, updated_at = :updated_at
    WHERE session_id = :session_id AND agent_id = :agent_id
    AND message_id = :message_id"""


def dumps(value: Any) -> str:
    return json.dumps(value, separators=(",", ":"), default=str)


def loads(value: str | None, fallback: Any) -> Any:
    if value is None:
        return fallback
    return json.loads(value)


def agent_params(session_id: str, agent: SessionAgent) -> dict[str, Any]:
    return {
        "session_id": session_id, "agent_id": agent.agent_id,
        "state": dumps(agent.state),
        "conversation_manager_state": dumps(agent.conversation_manager_state),
        "_internal_state": dumps(agent._internal_state),
        "created_at": agent.created_at, "updated_at": agent.updated_at,
    }


def agent_from_row(row: dict[str, Any]) -> SessionAgent:
    return SessionAgent.from_dict({
        "agent_id": row["agent_id"],
        "state": loads(row["state"], {}),
        "conversation_manager_state": loads(row["conversation_manager_state"], {}),
        "_internal_state": loads(row["_internal_state"], {}),
        "created_at": row["created_at"], "updated_at": row["updated_at"],
    })


def message_params(session_id: str, agent_id: str, msg: SessionMessage) -> dict[str, Any]:
    return {
        "session_id": session_id, "agent_id": agent_id,
        "message_id": msg.message_id, "message": dumps(msg.message),
        "redact_message": None if msg.redact_message is None else dumps(msg.redact_message),
        "created_at": msg.created_at, "updated_at": msg.updated_at,
    }


def message_from_row(row: dict[str, Any]) -> SessionMessage:
    return SessionMessage.from_dict({
        "message": loads(row["message"], {}),
        "message_id": int(row["message_id"]),
        "redact_message": loads(row["redact_message"], None),
        "created_at": row["created_at"], "updated_at": row["updated_at"],
    })


__all__ = [
    "AGENT_DDL", "AGENT_INSERT", "AGENT_UPDATE", "MESSAGE_DDL", "MESSAGE_INSERT",
    "MESSAGE_UPDATE", "SESSION_DDL", "SESSION_INSERT", "agent_from_row",
    "agent_params", "dumps", "loads", "message_from_row", "message_params",
]
