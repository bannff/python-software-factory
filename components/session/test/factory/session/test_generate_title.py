"""Behavior tests for ``session_generate_title`` (row 17 — auto title).

Mocks ``generate_title`` at the call site rather than the completion model
itself, so these tests exercise the real MCP tool's identity/revision/error
plumbing without needing real chat credentials — the completion callback
itself (``title_complete.py``) mirrors an already-tested pattern
(``memory``'s ``langchain_completion.py``) and is not re-tested here.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from factory.session.runtime.adapters.sql import SQLSessionStore
from factory.session.runtime.lifecycle import SessionLifecycle
from factory.session.runtime.runtime import SessionRuntime
from factory.session.runtime.title_generation import TitleGenerationError
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


def test_generate_title_applies_the_generated_title_via_rename(tmp_path: Path) -> None:
    tools = _tools(tmp_path)
    session = _create(tools)
    with patch(
        "factory.session.runtime.title_generation.generate_title",
        return_value="Deploy pipeline fix",
    ) as mock_generate:
        result = tools["session_generate_title"].fn(
            session_id=session.session_id, excerpt="user: fix the deploy\nassistant: done",
            expected_revision=session.revision, envelope=_env(),
        )
    assert result.ok is True
    assert result.data.session.title == "Deploy pipeline fix"
    mock_generate.assert_called_once_with("openrouter", "user: fix the deploy\nassistant: done")


def test_generate_title_is_revision_fenced_like_manual_rename(tmp_path: Path) -> None:
    tools = _tools(tmp_path)
    session = _create(tools)
    with patch(
        "factory.session.runtime.title_generation.generate_title",
        return_value="Title",
    ):
        stale = tools["session_generate_title"].fn(
            session_id=session.session_id, excerpt="x",
            expected_revision=session.revision + 1, envelope=_env(),
        )
    assert stale.ok is False and stale.error == "session_revision_conflict"


def test_generate_title_reports_completion_failure_without_writing(tmp_path: Path) -> None:
    tools = _tools(tmp_path)
    session = _create(tools)
    with patch(
        "factory.session.runtime.title_generation.generate_title",
        side_effect=TitleGenerationError("provider unavailable"),
    ):
        result = tools["session_generate_title"].fn(
            session_id=session.session_id, excerpt="x",
            expected_revision=session.revision, envelope=_env(),
        )
    assert result.ok is False and result.error == "session_title_generation_unavailable"
    unchanged = tools["session_get"].fn(session_id=session.session_id, envelope=_env())
    assert unchanged.data.session.title == "New session"


def test_generate_title_fails_closed_for_foreign_owner(tmp_path: Path) -> None:
    tools = _tools(tmp_path)
    session = _create(tools)
    result = tools["session_generate_title"].fn(
        session_id=session.session_id, excerpt="x",
        expected_revision=session.revision, envelope=_env("owner-b"),
    )
    assert result.ok is False and result.error == "session_not_found"
