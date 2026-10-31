"""Durable session tests for the strands chat adapter (phase 2 merge 3).

Restart durability (fresh agent instance over the same DB), fork parity,
AG-UI-shaped history rows. Fakes follow the ``_strands_*_fakes.py``
sibling convention; the repo takes an injected ``SQLStore`` or explicit
``db_path`` so tests never touch ``./.storage``.
"""
from __future__ import annotations

from typing import Any

import pytest

pytest.importorskip("strands")

from factory.agent.runtime.adapters.strands_history import session_messages_to_agui
from factory.agent.runtime.adapters.strands_session_repository import (
    SqlSessionRepository,
)
from strands.types.session import Session, SessionAgent, SessionMessage, SessionType

_PERSONA = "companion-x-default"


def _repo(tmp_path: Any) -> SqlSessionRepository:
    return SqlSessionRepository(db_path=str(tmp_path / "strands-sessions.db"))


def _seed_thread(repo: SqlSessionRepository, session_id: str, *, turns: int = 1) -> None:
    """Simulate what ``RepositorySessionManager`` writes for one turn."""
    repo.create_session(Session(session_id=session_id, session_type=SessionType.AGENT))
    repo.create_agent(session_id, SessionAgent.from_dict({
        "agent_id": _PERSONA, "state": {"turns": turns},
        "conversation_manager_state": {},
    }))
    for i in range(turns * 2):
        role = "user" if i % 2 == 0 else "assistant"
        repo.create_message(session_id, _PERSONA, SessionMessage.from_message(
            {"role": role, "content": [{"text": f"t{i}"}]}, i,
        ))


def test_restart_durability_over_same_db(tmp_path: Any) -> None:
    db = str(tmp_path / "strands-sessions.db")
    first = SqlSessionRepository(db_path=db)
    _seed_thread(first, f"{_PERSONA}-dur-thread")

    restarted = SqlSessionRepository(db_path=db)
    agent = restarted.read_agent(f"{_PERSONA}-dur-thread", _PERSONA)
    assert agent is not None and agent.state == {"turns": 1}
    messages = restarted.list_messages(f"{_PERSONA}-dur-thread", _PERSONA)
    assert [m.message_id for m in messages] == [0, 1]
    assert messages[1].to_message()["content"][0]["text"] == "t1"


def test_fork_parity_and_independence(tmp_path: Any) -> None:
    repo = _repo(tmp_path)
    source = f"{_PERSONA}-src"
    _seed_thread(repo, source, turns=2)
    target = f"{_PERSONA}-fork"

    assert repo.fork_session(source, target) is True
    source_rows = repo.list_messages(source, _PERSONA)
    target_rows = repo.list_messages(target, _PERSONA)
    assert [m.message for m in target_rows] == [m.message for m in source_rows]
    assert [m.message_id for m in target_rows] == [0, 1, 2, 3]

    # Post-fork independence: appending to the target leaves source alone.
    repo.create_message(target, _PERSONA, SessionMessage.from_message(
        {"role": "user", "content": [{"text": "post-fork"}]}, 4,
    ))
    assert len(repo.list_messages(source, _PERSONA)) == 4
    assert len(repo.list_messages(target, _PERSONA)) == 5
    # Source agent state unmutated by the fork.
    assert repo.read_agent(source, _PERSONA).state == {"turns": 2}
    assert repo.read_agent(target, _PERSONA).state == {"turns": 2}


def test_fork_false_on_empty_or_missing_source(tmp_path: Any) -> None:
    repo = _repo(tmp_path)
    repo.create_session(Session(session_id="empty-t", session_type=SessionType.AGENT))
    assert repo.fork_session("empty-t", "empty-fork") is False
    assert repo.fork_session("never-existed", "x") is False
    assert repo.read_session("empty-fork") is None


def test_delete_session_drops_all_rows(tmp_path: Any) -> None:
    repo = _repo(tmp_path)
    _seed_thread(repo, f"{_PERSONA}-gone")
    repo.delete_session(f"{_PERSONA}-gone")
    assert repo.read_session(f"{_PERSONA}-gone") is None
    assert repo.read_agent(f"{_PERSONA}-gone", _PERSONA) is None
    assert repo.list_messages(f"{_PERSONA}-gone", _PERSONA) == []


def test_history_rows_are_agui_shaped(tmp_path: Any) -> None:
    repo = _repo(tmp_path)
    session_id = f"{_PERSONA}-hist"
    repo.create_session(Session(session_id=session_id, session_type=SessionType.AGENT))
    repo.create_agent(session_id, SessionAgent.from_dict({
        "agent_id": _PERSONA, "state": {}, "conversation_manager_state": {},
    }))
    rows_in = [
        {"role": "user", "content": [{"text": "hi"}]},
        {"role": "assistant", "content": [{"text": "calling"}],
         "toolUses": [{"toolUseId": "tu1", "name": "demo_tool", "input": {"a": 1}}]},
        {"role": "tool", "content": [{"text": "r"}], "toolUseId": "tu1"},
    ]
    for i, message in enumerate(rows_in):
        repo.create_message(session_id, _PERSONA, SessionMessage.from_message(message, i))

    from factory.agent.mcp.session_history import HistoryMessage
    projected = session_messages_to_agui(repo, session_id)
    parsed = [HistoryMessage.model_validate(row) for row in projected]
    assert [p.role for p in parsed] == ["user", "assistant", "tool"]
    assert parsed[1].tool_calls[0].function.name == "demo_tool"
    assert parsed[1].tool_calls[0].function.arguments == '{"a":1}'
    assert parsed[2].tool_call_id == "tu1"
