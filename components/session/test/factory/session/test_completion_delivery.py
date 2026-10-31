from __future__ import annotations

import pytest

from factory.session.runtime.adapters.completion_sql import SQLCompletionStore
from factory.session.runtime.adapters.sql import SQLSessionStore
from factory.session.runtime.completion import CompletionLifecycle
from factory.session.runtime.errors import SessionConflictError
from factory.session.runtime.lifecycle import SessionLifecycle
from factory.session.runtime.runtime import SessionRuntime
from factory.storage.interface import StorageRuntime


def _runtime(path: str):
    sql = StorageRuntime().get_sql_store("sqlite", db_path=path)
    sessions = SQLSessionStore(sql)
    return SessionLifecycle(sessions), CompletionLifecycle(SQLCompletionStore(sql), sessions)


def test_completion_is_deduplicated_and_acknowledged_once(tmp_path) -> None:
    sessions, completions = _runtime(str(tmp_path / "session.db"))
    session = sessions.create("tenant", "owner", "origin", "agent", "model")
    summary = "Background work completed."
    digest = completions.digest("ok", summary)
    first = completions.record(
        "tenant", "owner", session.session_id, "run:1", "ok", summary, digest, 1,
    )
    replay = completions.record(
        "tenant", "owner", session.session_id, "run:1", "ok", summary, digest, 1,
    )
    assert replay == first
    assert completions.pending("tenant", "owner", session.session_id) == [first]
    delivered = completions.acknowledge(
        "tenant", "owner", session.session_id, "run:1", digest, 1,
    )
    assert delivered.state.value == "delivered" and delivered.revision == 2
    assert completions.pending("tenant", "owner", session.session_id) == []
    with pytest.raises(SessionConflictError):
        completions.acknowledge(
            "tenant", "owner", session.session_id, "run:1", digest, 1,
        )


def test_pending_completion_survives_runtime_reconstruction(tmp_path) -> None:
    path = str(tmp_path / "restart.db")
    sessions, completions = _runtime(path)
    session = sessions.create("tenant", "owner", "origin", "agent", "model")
    digest = completions.digest("failed", "Background work failed.")
    completions.record(
        "tenant", "owner", session.session_id, "run:2", "failed",
        "Background work failed.", digest, 1,
    )
    _, restarted = _runtime(path)
    assert [item.run_id for item in restarted.pending(
        "tenant", "owner", session.session_id,
    )] == ["run:2"]


def test_session_list_derives_unread_from_pending_completion(tmp_path) -> None:
    sessions, completions = _runtime(str(tmp_path / "unread.db"))
    runtime = SessionRuntime(sessions, completions)
    session = sessions.create("tenant", "owner", "origin", "agent", "model")
    summary = "Background work completed."
    digest = completions.digest("ok", summary)
    assert runtime.list_sessions("tenant", "owner")[0].unread is False
    completion = completions.record(
        "tenant", "owner", session.session_id, "run:unread", "ok", summary, digest, 1,
    )
    assert runtime.list_sessions("tenant", "owner")[0].unread is True
    assert runtime.get_session("tenant", "owner", session.session_id).unread is True
    completions.acknowledge(
        "tenant", "owner", session.session_id, completion.run_id,
        completion.result_digest, completion.revision,
    )
    assert runtime.list_sessions("tenant", "owner")[0].unread is False
