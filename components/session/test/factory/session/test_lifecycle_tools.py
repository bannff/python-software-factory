"""Behavior tests for typed session lifecycle and steering tools."""
from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from factory.mcp_utils.runtime.schema_migration import SchemaMigrationError
from factory.session.runtime.adapters.sql import SQLSessionStore
from factory.session.runtime.lifecycle import SessionConflictError, SessionLifecycle
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


def test_lifecycle_tools_are_typed_and_classified(tmp_path: Path) -> None:
    tools = _tools(tmp_path)
    operational = {
        "session_create", "session_rename", "session_archive", "session_reopen",
        "session_set_model", "session_rebind", "session_set_pinned",
        "session_move_pinned", "session_set_tags", "session_set_pinned_messages",
        "session_steer", "session_acknowledge_steer", "session_requeue_steer",
    }
    deterministic = {"session_get", "session_list", "session_get_steer"}
    assert operational | deterministic <= set(tools)
    for name in operational | deterministic:
        fn = tools[name].fn
        expected = "operational" if name in operational else "deterministic"
        assert getattr(fn, "_mcp_category") == expected
        assert getattr(fn, "_mcp_input_model") is not None
        assert getattr(fn, "_mcp_output_model") is not None
    ack = tools["session_acknowledge_steer"].fn
    assert getattr(ack, "_mcp_service_callers") == frozenset({"agent"})
    assert getattr(ack, "_mcp_service_binding") == "steer"


def test_create_get_list_rename_archive_reopen(tmp_path: Path) -> None:
    tools = _tools(tmp_path)
    created = _create(tools)
    listed = tools["session_list"].fn(envelope=_env())
    assert [item.session_id for item in listed.data.sessions] == [created.session_id]
    fetched = tools["session_get"].fn(
        session_id=created.session_id, envelope=_env(),
    )
    assert fetched.data.session.thread_id == created.thread_id

    renamed = tools["session_rename"].fn(
        session_id=created.session_id, title="Renamed",
        expected_revision=created.revision, envelope=_env(),
    )
    assert renamed.data.session.title == "Renamed"
    archived = tools["session_archive"].fn(
        session_id=created.session_id,
        expected_revision=renamed.data.session.revision, envelope=_env(),
    )
    assert archived.data.session.archived_at is not None
    assert tools["session_list"].fn(envelope=_env()).data.sessions == []
    reopened = tools["session_reopen"].fn(
        session_id=created.session_id,
        expected_revision=archived.data.session.revision, envelope=_env(),
    )
    assert reopened.data.session.archived_at is None


def test_pin_and_manual_order_tools_are_owner_scoped_and_cas_fenced(tmp_path: Path) -> None:
    tools = _tools(tmp_path)
    one = _create(tools)
    two = _create(tools)
    pinned_one = tools["session_set_pinned"].fn(
        session_id=one.session_id, pinned=True,
        expected_revision=one.revision, envelope=_env(),
    ).data.session
    pinned_two = tools["session_set_pinned"].fn(
        session_id=two.session_id, pinned=True,
        expected_revision=two.revision, envelope=_env(),
    ).data.session
    assert [item.session_id for item in tools["session_list"].fn(
        envelope=_env(),
    ).data.sessions][:2] == [one.session_id, two.session_id]
    tagged = tools["session_set_tags"].fn(
        session_id=one.session_id, tags=("urgent", "review"),
        expected_revision=pinned_one.revision, envelope=_env(),
    ).data.session
    assert tagged.tags == ("urgent", "review")

    moved = tools["session_move_pinned"].fn(
        session_id=two.session_id, before_session_id=one.session_id,
        expected_revision=pinned_two.revision, envelope=_env(),
    ).data.session
    assert [item.session_id for item in tools["session_list"].fn(
        envelope=_env(),
    ).data.sessions][:2] == [two.session_id, one.session_id]
    stale = tools["session_set_pinned"].fn(
        session_id=one.session_id, pinned=False,
        expected_revision=one.revision, envelope=_env(),
    )
    assert not stale.ok and stale.error == "session_revision_conflict"
    archived = tools["session_archive"].fn(
        session_id=two.session_id, expected_revision=moved.revision,
        envelope=_env(),
    ).data.session
    assert archived.pinned_rank is None
    assert pinned_one.pinned_rank is not None


def test_missing_or_foreign_identity_fails_closed(tmp_path: Path) -> None:
    tools = _tools(tmp_path)
    denied = tools["session_create"].fn(
        title="No identity", agent_id="companion-x-default", model="openrouter",
    )
    assert denied.ok is False and denied.error == "session_identity_required"
    created = _create(tools)
    foreign = tools["session_get"].fn(
        session_id=created.session_id, envelope=_env("owner-b"),
    )
    assert foreign.ok is False and foreign.error == "session_not_found"


def test_session_create_reports_the_real_error_for_a_refused_project_path(tmp_path: Path) -> None:
    """A previously-swallowed bug (found live 2026-09-16, row 17 cycle):
    an out-of-allowed-roots project path used to propagate uncaught,
    flattening to a generic tool_execution_failed at the MCP boundary.
    Uses a real, existing directory outside the allowed roots (the actual
    live bug: the path existed, it was just outside
    COMPANION_X_PROJECT_ALLOWED_ROOTS) — a nonexistent path raises
    FileNotFoundError even earlier, a different failure mode."""
    tools = _tools(tmp_path)
    outside_root = tmp_path / "outside-allowed-roots"
    outside_root.mkdir()
    result = tools["session_create"].fn(
        title="New session", agent_id="companion-x-default", model="openrouter",
        project=str(outside_root), envelope=_env(),
    )
    assert result.ok is False and result.error == "session_project_path_refused"


def test_session_delete_removes_the_session_and_is_revision_fenced(tmp_path: Path) -> None:
    """Row 8 (feature-map) — "Older sessions" per-session delete."""
    tools = _tools(tmp_path)
    session = _create(tools)
    stale = tools["session_delete"].fn(
        session_id=session.session_id, expected_revision=session.revision + 1,
        envelope=_env(),
    )
    assert stale.ok is False and stale.error == "session_revision_conflict"
    deleted = tools["session_delete"].fn(
        session_id=session.session_id, expected_revision=session.revision,
        envelope=_env(),
    )
    assert deleted.ok is True and deleted.data.deleted is True
    gone = tools["session_get"].fn(session_id=session.session_id, envelope=_env())
    assert gone.ok is False and gone.error == "session_not_found"


def test_session_delete_fails_closed_for_foreign_owner(tmp_path: Path) -> None:
    tools = _tools(tmp_path)
    session = _create(tools)
    result = tools["session_delete"].fn(
        session_id=session.session_id, expected_revision=session.revision,
        envelope=_env("owner-b"),
    )
    assert result.ok is False and result.error == "session_not_found"
    still_there = tools["session_get"].fn(session_id=session.session_id, envelope=_env())
    assert still_there.ok is True


def test_clear_archived_deletes_only_archived_sessions_and_matches_the_count(tmp_path: Path) -> None:
    """Row 8 (feature-map) bulk "Delete all"."""
    tools = _tools(tmp_path)
    active = _create(tools)
    to_archive = _create(tools)
    archived = tools["session_archive"].fn(
        session_id=to_archive.session_id, expected_revision=to_archive.revision,
        envelope=_env(),
    ).data.session
    assert archived.archived_at is not None

    count = tools["session_count_archived"].fn(envelope=_env())
    assert count.ok is True and count.data.count == 1

    cleared = tools["session_clear_archived"].fn(envelope=_env())
    assert cleared.ok is True and cleared.data.deleted_count == 1

    # the active (non-archived) session is untouched
    still_active = tools["session_get"].fn(session_id=active.session_id, envelope=_env())
    assert still_active.ok is True
    # the archived one is genuinely gone, not just re-archived
    gone = tools["session_get"].fn(session_id=to_archive.session_id, envelope=_env())
    assert gone.ok is False and gone.error == "session_not_found"

    # idempotent: nothing left to clear
    recount = tools["session_count_archived"].fn(envelope=_env())
    assert recount.data.count == 0
    recleared = tools["session_clear_archived"].fn(envelope=_env())
    assert recleared.data.deleted_count == 0


def test_clear_archived_is_owner_scoped(tmp_path: Path) -> None:
    tools = _tools(tmp_path)
    mine = _create(tools)
    tools["session_archive"].fn(
        session_id=mine.session_id, expected_revision=mine.revision, envelope=_env(),
    )
    # a different owner's clear-all never touches this owner's archived session
    cleared = tools["session_clear_archived"].fn(envelope=_env("owner-b"))
    assert cleared.ok is True and cleared.data.deleted_count == 0
    still_there = tools["session_get"].fn(session_id=mine.session_id, envelope=_env())
    assert still_there.ok is True


def test_steer_deduplicates_and_archived_session_rejects(tmp_path: Path) -> None:
    tools = _tools(tmp_path)
    session = _create(tools)
    first = tools["session_steer"].fn(
        session_id=session.session_id, send_id="send_1",
        content="Use the new constraint", envelope=_env(),
    )
    duplicate = tools["session_steer"].fn(
        session_id=session.session_id, send_id="send_1",
        content="Different text is ignored", envelope=_env(),
    )
    assert first.ok and duplicate.ok
    assert duplicate.data.steer.delivery_id == first.data.steer.delivery_id
    archived = tools["session_archive"].fn(
        session_id=session.session_id, expected_revision=session.revision,
        envelope=_env(),
    ).data.session
    rejected = tools["session_steer"].fn(
        session_id=session.session_id, send_id="send_2",
        content="Must not persist", envelope=_env(),
    )
    assert rejected.ok is False and rejected.error == "session_not_found"
    assert archived.archived_at is not None


@pytest.mark.parametrize("send_id", [
    "AKIAIOSFODNN7EXAMPLE",
    "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghij",
    "sk-proj_ABCDEFGHIJKLMNOPQRSTUVWXYZ123456",
])
def test_steer_rejects_credential_shaped_send_ids(
    tmp_path: Path, send_id: str,
) -> None:
    tools = _tools(tmp_path)
    session = _create(tools)
    result = tools["session_steer"].fn(
        session_id=session.session_id, send_id=send_id,
        content="safe text", envelope=_env(),
    )
    assert result.ok is False and result.error == "send_id_rejected"


def test_steer_models_remain_strict(tmp_path: Path) -> None:
    model = getattr(_tools(tmp_path)["session_steer"].fn, "_mcp_input_model")
    with pytest.raises(ValidationError):
        model.model_validate({
            "session_id": "session_1", "send_id": "send_1", "content": "x",
            "envelope": _env(), "unexpected": True,
        })


def test_agent_requeue_is_terminal_and_revision_fenced(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path).lifecycle
    tenant_id, owner_id = runtime.identity(_env())
    session = runtime.create(
        tenant_id, owner_id, "Session", "companion-x-default", "openrouter",
    )
    written = runtime.steer(
        tenant_id, owner_id, session.session_id, "send_requeue", "later",
    )
    requeued = runtime.requeue(
        tenant_id, owner_id, session.session_id,
        written.delivery_id, written.revision,
    )
    assert requeued.state.value == "requeued" and requeued.revision == 2
    with pytest.raises(SessionConflictError):
        runtime.requeue(
            tenant_id, owner_id, session.session_id,
            written.delivery_id, written.revision,
        )
    tool = _tools(tmp_path)["session_requeue_steer"].fn
    assert getattr(tool, "_mcp_service_callers") == frozenset({"agent"})
    assert getattr(tool, "_mcp_service_binding") == "steer"


def test_ensure_thread_is_owner_scoped_and_idempotent(tmp_path: Path) -> None:
    tools = _tools(tmp_path)
    first = tools["session_ensure_thread"].fn(
        thread_id="thread-chat", title="First prompt",
        agent_id="companion-x-default", model="openrouter", envelope=_env(),
    )
    second = tools["session_ensure_thread"].fn(
        thread_id="thread-chat", title="Ignored replacement",
        agent_id="companion-x-default", model="openrouter", envelope=_env(),
    )
    assert first.ok and second.ok
    assert first.data.session.session_id == second.data.session.session_id
    assert second.data.session.title == "First prompt"
    assert len(tools["session_list"].fn(envelope=_env()).data.sessions) == 1
    foreign = tools["session_resolve_thread"].fn(
        thread_id="thread-chat", envelope=_env("owner-b"),
    )
    assert foreign.ok is False and foreign.error == "session_not_found"


def test_ensure_thread_mode_round_trips_through_the_real_mcp_boundary(
    tmp_path: Path,
) -> None:
    """Row 3 (feature-map): the caller-resolved default/explicit mode must
    reach the real typed tool, not just the lifecycle layer directly."""
    tools = _tools(tmp_path)
    created = tools["session_ensure_thread"].fn(
        thread_id="thread-incognito", title="Sensitive question",
        agent_id="companion-x-default", model="openrouter",
        mode="incognito", envelope=_env(),
    )
    assert created.ok and created.data.session.mode == "incognito"
    with pytest.raises(SchemaMigrationError):
        tools["session_ensure_thread"].fn(
            thread_id="thread-bogus", title="x",
            agent_id="companion-x-default", model="openrouter",
            mode="not-a-real-mode", envelope=_env(),
        )


def test_ensure_thread_project_round_trips_through_the_real_mcp_boundary(
    tmp_path: Path, monkeypatch,
) -> None:
    """Chat-created Sessions must be able to bind a devtools project at
    creation: session steering passes COMPANION_X_DEFAULT_PROJECT through
    ensure_thread; without the project the devtools binding chain rejects
    every chat thread (``Session has no project binding``). The project
    goes through the same canonical validator as create/bind (PathRefused
    → typed rejection), idempotent re-ensure keeps the original binding,
    and a bad project fails closed."""
    allowed = tmp_path / "projects"
    allowed.mkdir()
    monkeypatch.setenv("COMPANION_X_PROJECT_ALLOWED_ROOTS", str(allowed))
    root = tmp_path / "projects" / "repo"
    root.mkdir()
    (root / "pyproject.toml").write_text("[project]\nname='fixture'\n")
    tools = _tools(tmp_path)
    created = tools["session_ensure_thread"].fn(
        thread_id="thread-project", title="Repo question",
        agent_id="companion-x-default", model="openrouter",
        project=str(root), envelope=_env(),
    )
    assert created.ok and created.data.session.project == str(root.resolve())
    rebound = tools["session_ensure_thread"].fn(
        thread_id="thread-project", title="Repo question",
        agent_id="companion-x-default", model="openrouter",
        envelope=_env(),
    )
    assert rebound.ok
    assert rebound.data.session.session_id == created.data.session.session_id
    # Real, existing directory OUTSIDE the allowed roots — the live-bug
    # failure mode (a nonexistent path raises FileNotFoundError even
    # earlier; see test_session_create_reports_the_real_error_for_a_refused_project_path).
    outside = tmp_path / "outside-allowed-roots"
    outside.mkdir()
    rejected = tools["session_ensure_thread"].fn(
        thread_id="thread-bad-project", title="x",
        agent_id="companion-x-default", model="openrouter",
        project=str(outside), envelope=_env(),
    )
    assert rejected.ok is False and rejected.error == "session_project_path_refused"


def test_session_fork_round_trips_through_the_real_mcp_boundary(
    tmp_path: Path,
) -> None:
    """Row 14 (feature-map): forking through the real typed tool creates
    a genuine second session, listable independently, carrying the
    source's exact bindings, and is owner-scoped like every other tool."""
    tools = _tools(tmp_path)
    source = tools["session_create"].fn(
        title="Original", agent_id="companion-x-default", model="openrouter",
        mode="temporary", envelope=_env(),
    ).data.session
    forked = tools["session_fork"].fn(
        session_id=source.session_id, envelope=_env(),
    )
    assert forked.ok
    assert forked.data.session.session_id != source.session_id
    assert forked.data.session.mode == "temporary"
    assert forked.data.session.title == "Original (fork)"
    listed = tools["session_list"].fn(envelope=_env()).data.sessions
    assert {item.session_id for item in listed} == {
        source.session_id, forked.data.session.session_id,
    }
    foreign = tools["session_fork"].fn(
        session_id=source.session_id, envelope=_env("owner-b"),
    )
    assert foreign.ok is False and foreign.error == "session_not_found"


def test_mcp_identity_uses_authenticated_ambient_and_denies_override(tmp_path: Path) -> None:
    from factory.mcp_utils.interface import reset_envelope, set_envelope

    tools = _tools(tmp_path)
    token = set_envelope(_env())
    try:
        created = tools["session_create"].fn(
            title="Ambient", agent_id="companion-x-default", model="openrouter",
        )
        assert created.ok is True
        denied = tools["session_list"].fn(envelope=_env("owner-b"))
        assert denied.ok is False and denied.error == "session_identity_required"
    finally:
        reset_envelope(token)
