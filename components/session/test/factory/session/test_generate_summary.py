"""Behavior tests for row 18 (feature-map) — session rolling summary.

``generate_summary`` is mocked at the call site (like ``test_generate_title``)
so these exercise the real MCP tool's identity/revision/error plumbing and
the real ``set_summary`` SQL round-trip without needing chat credentials.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from factory.session.runtime.adapters.sql import SQLSessionStore
from factory.session.runtime.lifecycle import SessionLifecycle
from factory.session.runtime.runtime import SessionRuntime
from factory.session.runtime.summary_generation import SummaryGenerationError
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


_TRANSCRIPT = "user: deploy the fix\nassistant: shipped, then rolled back once"
_SUMMARY = "Discussed a deploy fix; shipped then rolled back. Open: root cause."


def test_new_session_starts_with_an_empty_summary(tmp_path: Path) -> None:
    tools = _tools(tmp_path)
    session = _create(tools)
    assert session.summary == ""


def test_generate_summary_applies_and_persists_via_set_summary(tmp_path: Path) -> None:
    tools = _tools(tmp_path)
    session = _create(tools)
    with patch(
        "factory.session.runtime.summary_generation.generate_summary",
        return_value=_SUMMARY,
    ) as mock_generate:
        result = tools["session_generate_summary"].fn(
            session_id=session.session_id, excerpt=_TRANSCRIPT,
            expected_revision=session.revision, envelope=_env(),
        )
    assert result.ok is True
    assert result.data.session.summary == _SUMMARY
    assert result.data.session.revision == session.revision + 1
    mock_generate.assert_called_once_with("openrouter", _TRANSCRIPT)
    # Durable: a fresh read (not just the mutation's own return) shows it.
    reread = tools["session_get"].fn(session_id=session.session_id, envelope=_env())
    assert reread.data.session.summary == _SUMMARY


def test_generate_summary_is_revision_fenced(tmp_path: Path) -> None:
    tools = _tools(tmp_path)
    session = _create(tools)
    with patch(
        "factory.session.runtime.summary_generation.generate_summary",
        return_value=_SUMMARY,
    ):
        stale = tools["session_generate_summary"].fn(
            session_id=session.session_id, excerpt=_TRANSCRIPT,
            expected_revision=session.revision + 1, envelope=_env(),
        )
    assert stale.ok is False and stale.error == "session_revision_conflict"


def test_generate_summary_reports_completion_failure_without_writing(tmp_path: Path) -> None:
    tools = _tools(tmp_path)
    session = _create(tools)
    with patch(
        "factory.session.runtime.summary_generation.generate_summary",
        side_effect=SummaryGenerationError("provider unavailable"),
    ):
        result = tools["session_generate_summary"].fn(
            session_id=session.session_id, excerpt=_TRANSCRIPT,
            expected_revision=session.revision, envelope=_env(),
        )
    assert result.ok is False and result.error == "session_summary_generation_unavailable"
    unchanged = tools["session_get"].fn(session_id=session.session_id, envelope=_env())
    assert unchanged.data.session.summary == ""


def test_generate_summary_fails_closed_for_foreign_owner(tmp_path: Path) -> None:
    tools = _tools(tmp_path)
    session = _create(tools)
    result = tools["session_generate_summary"].fn(
        session_id=session.session_id, excerpt=_TRANSCRIPT,
        expected_revision=session.revision, envelope=_env("owner-b"),
    )
    assert result.ok is False and result.error == "session_not_found"


def test_set_summary_survives_a_reopened_store(tmp_path: Path) -> None:
    """The summary column persists across a store restart (additive-column
    migration path), not just in one process's memory."""
    db = str(tmp_path / "session.db")
    sql = StorageRuntime().get_sql_store("sqlite", db_path=db)
    store = SQLSessionStore(sql)
    lifecycle = SessionLifecycle(store)
    session = lifecycle.create("tenant-a", "owner-a", "S", "companion-x-default", "openrouter")
    lifecycle.set_summary("tenant-a", "owner-a", session.session_id, _SUMMARY, session.revision)

    reopened = SQLSessionStore(StorageRuntime().get_sql_store("sqlite", db_path=db))
    fetched = reopened.get("tenant-a", "owner-a", session.session_id)
    assert fetched is not None and fetched.summary == _SUMMARY
