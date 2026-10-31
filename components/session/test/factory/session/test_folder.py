"""Behavior tests for row 6 (feature-map) — session folder filing."""
from __future__ import annotations

from pathlib import Path

from factory.session.runtime.adapters.sql import SQLSessionStore
from factory.session.runtime.lifecycle import SessionLifecycle
from factory.session.runtime.runtime import SessionRuntime
from factory.session.server import create_tool_catalog
from factory.storage.interface import StorageRuntime


def _tools(tmp_path: Path):
    sql = StorageRuntime().get_sql_store("sqlite", db_path=str(tmp_path / "session.db"))
    runtime = SessionRuntime(SessionLifecycle(SQLSessionStore(sql)))
    return create_tool_catalog(runtime).tool_map()


def _env(owner: str = "owner-a") -> dict[str, str]:
    return {"tenant_id": "tenant-a", "principal_id": owner}


def _create(tools):
    result = tools["session_create"].fn(
        title="New session", agent_id="companion-x-default", model="openrouter",
        envelope=_env(),
    )
    assert result.ok is True
    return result.data.session


def test_new_session_is_unfiled(tmp_path: Path) -> None:
    assert _create(_tools(tmp_path)).folder == ""


def test_set_folder_files_and_clears_the_session(tmp_path: Path) -> None:
    tools = _tools(tmp_path)
    session = _create(tools)
    filed = tools["session_set_folder"].fn(
        session_id=session.session_id, folder="Client work",
        expected_revision=session.revision, envelope=_env(),
    )
    assert filed.ok and filed.data.session.folder == "Client work"
    reread = tools["session_get"].fn(session_id=session.session_id, envelope=_env())
    assert reread.data.session.folder == "Client work"

    cleared = tools["session_set_folder"].fn(
        session_id=session.session_id, folder="",
        expected_revision=filed.data.session.revision, envelope=_env(),
    )
    assert cleared.ok and cleared.data.session.folder == ""


def test_set_folder_is_revision_fenced(tmp_path: Path) -> None:
    tools = _tools(tmp_path)
    session = _create(tools)
    stale = tools["session_set_folder"].fn(
        session_id=session.session_id, folder="X",
        expected_revision=session.revision + 1, envelope=_env(),
    )
    assert stale.ok is False and stale.error == "session_revision_conflict"


def test_set_folder_fails_closed_for_foreign_owner(tmp_path: Path) -> None:
    tools = _tools(tmp_path)
    session = _create(tools)
    result = tools["session_set_folder"].fn(
        session_id=session.session_id, folder="X",
        expected_revision=session.revision, envelope=_env("owner-b"),
    )
    assert result.ok is False and result.error == "session_not_found"


def test_folder_survives_a_reopened_store(tmp_path: Path) -> None:
    db = str(tmp_path / "session.db")
    store = SQLSessionStore(StorageRuntime().get_sql_store("sqlite", db_path=db))
    lifecycle = SessionLifecycle(store)
    session = lifecycle.create("tenant-a", "owner-a", "S", "companion-x-default", "openrouter")
    lifecycle.set_folder("tenant-a", "owner-a", session.session_id, "Archive 2026", session.revision)

    reopened = SQLSessionStore(StorageRuntime().get_sql_store("sqlite", db_path=db))
    fetched = reopened.get("tenant-a", "owner-a", session.session_id)
    assert fetched is not None and fetched.folder == "Archive 2026"
