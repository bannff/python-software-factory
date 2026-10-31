"""session_set_active_checkpoint MCP tool — row 16 substrate (pin which
checkpoint branch is "current" for a thread once a regenerate/variant
switch has created sibling branches)."""
from __future__ import annotations

from pathlib import Path

from factory.session.runtime.adapters.sql import SQLSessionStore
from factory.session.runtime.lifecycle import SessionLifecycle
from factory.session.runtime.runtime import SessionRuntime
from factory.session.server import create_tool_catalog
from factory.storage.interface import StorageRuntime


def _runtime(tmp_path: Path) -> SessionRuntime:
    sql = StorageRuntime().get_sql_store("sqlite", db_path=str(tmp_path / "session.db"))
    return SessionRuntime(SessionLifecycle(SQLSessionStore(sql)))


def _tools(tmp_path: Path):
    return create_tool_catalog(_runtime(tmp_path)).tool_map()


def _env(owner: str = "owner-a") -> dict[str, str]:
    return {"tenant_id": "tenant-a", "principal_id": owner}


def _create(tools):
    result = tools["session_create"].fn(
        title="New session", agent_id="companion-x-default", model="openrouter",
        envelope=_env(),
    )
    assert result.ok is True
    return result.data.session


def test_set_active_checkpoint_pins_a_branch_through_the_real_tool(tmp_path: Path) -> None:
    tools = _tools(tmp_path)
    created = _create(tools)
    assert created.active_checkpoint_id is None

    result = tools["session_set_active_checkpoint"].fn(
        session_id=created.session_id, checkpoint_id="ckpt-abc",
        expected_revision=created.revision, envelope=_env(),
    )

    assert result.ok is True
    assert result.data.session.active_checkpoint_id == "ckpt-abc"
    assert result.data.session.revision == created.revision + 1


def test_set_active_checkpoint_can_clear_the_pointer_through_the_real_tool(tmp_path: Path) -> None:
    tools = _tools(tmp_path)
    created = _create(tools)
    pinned = tools["session_set_active_checkpoint"].fn(
        session_id=created.session_id, checkpoint_id="ckpt-abc",
        expected_revision=created.revision, envelope=_env(),
    ).data.session

    result = tools["session_set_active_checkpoint"].fn(
        session_id=created.session_id, checkpoint_id=None,
        expected_revision=pinned.revision, envelope=_env(),
    )

    assert result.ok is True
    assert result.data.session.active_checkpoint_id is None


def test_set_active_checkpoint_rejects_a_stale_revision(tmp_path: Path) -> None:
    tools = _tools(tmp_path)
    created = _create(tools)
    result = tools["session_set_active_checkpoint"].fn(
        session_id=created.session_id, checkpoint_id="ckpt-abc",
        expected_revision=created.revision + 1, envelope=_env(),
    )
    assert result.ok is False and result.error == "session_revision_conflict"


def test_set_active_checkpoint_rejects_an_unknown_session(tmp_path: Path) -> None:
    tools = _tools(tmp_path)
    _create(tools)
    result = tools["session_set_active_checkpoint"].fn(
        session_id="s_missing", checkpoint_id="ckpt-abc",
        expected_revision=1, envelope=_env(),
    )
    assert result.ok is False and result.error == "session_not_found"


def test_set_active_checkpoint_is_owner_scoped(tmp_path: Path) -> None:
    tools = _tools(tmp_path)
    created = _create(tools)
    result = tools["session_set_active_checkpoint"].fn(
        session_id=created.session_id, checkpoint_id="ckpt-abc",
        expected_revision=created.revision, envelope=_env("owner-b"),
    )
    assert result.ok is False and result.error == "session_not_found"
