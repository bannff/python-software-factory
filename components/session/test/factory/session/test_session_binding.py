"""Slice-3 tests: crew/memory materialization, set-model, and CAS rebind."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from factory.session.runtime.adapters.sql import SQLSessionStore
from factory.session.runtime.errors import (
    SessionBindingRejectedError, SessionConflictError, SessionNotFoundError,
)
from factory.session.runtime.lifecycle import SessionLifecycle
from factory.session.server import create_tool_catalog
from factory.session.runtime.runtime import SessionRuntime
from factory.storage.interface import StorageRuntime

TENANT = "tenant-a"
OWNER = "owner-a"
MODEL = "anthropic.claude-sonnet"  # bedrock-shaped id resolves without env/secrets

# Pre-M6.5 table definition, deliberately missing the new binding columns.
_LEGACY_SCHEMA = """
CREATE TABLE companion_sessions (
  tenant_id TEXT NOT NULL, owner_id TEXT NOT NULL, session_id TEXT NOT NULL,
  thread_id TEXT NOT NULL, title TEXT NOT NULL, agent_id TEXT NOT NULL,
  model TEXT NOT NULL, mode TEXT NOT NULL, workspace TEXT NOT NULL,
  project TEXT NOT NULL, origin TEXT NOT NULL, created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL, archived_at TEXT, revision INTEGER NOT NULL,
  PRIMARY KEY (tenant_id, owner_id, session_id)
)
"""


def _sql(path: Path):
    return StorageRuntime().get_sql_store("sqlite", db_path=str(path))


def _life(path: Path) -> SessionLifecycle:
    return SessionLifecycle(SQLSessionStore(_sql(path)))


def test_create_materializes_crew_and_memory_scope(tmp_path: Path) -> None:
    life = _life(tmp_path / "s.db")
    created = life.create(
        TENANT, OWNER, "t", "companion-x-default", MODEL,
        crew_id="redteam-crew", memory_scope="redteam",
    )
    assert created.crew_id == "redteam-crew"
    assert created.memory_scope == "redteam"
    reread = life.get(TENANT, OWNER, created.session_id)
    assert reread == created


def test_ensure_thread_materializes_binding_once(tmp_path: Path) -> None:
    life = _life(tmp_path / "s.db")
    first = life.ensure_thread(
        TENANT, OWNER, "thr-1", "t", "companion-x-default", MODEL,
        crew_id="crew-a", memory_scope="scope-a",
    )
    again = life.ensure_thread(
        TENANT, OWNER, "thr-1", "ignored", "companion-x-default", MODEL,
        crew_id="crew-b", memory_scope="scope-b",
    )
    assert again.session_id == first.session_id
    assert again.crew_id == "crew-a" and again.memory_scope == "scope-a"


def test_ensure_thread_carries_the_memory_mode(tmp_path: Path) -> None:
    """Row 3 (feature-map): a caller-resolved default (or explicit per-chat
    choice) must actually land on the materialized session, and the FIRST
    ensure_thread call wins the same way crew_id/memory_scope already do."""
    life = _life(tmp_path / "s.db")
    created = life.ensure_thread(
        TENANT, OWNER, "thr-mode", "t", "companion-x-default", MODEL,
        mode="incognito",
    )
    assert created.mode == "incognito"
    again = life.ensure_thread(
        TENANT, OWNER, "thr-mode", "ignored", "companion-x-default", MODEL,
        mode="temporary",
    )
    assert again.mode == "incognito"


def test_fork_creates_a_new_session_with_the_same_bindings(tmp_path: Path) -> None:
    """Row 14 (feature-map): a fork's child carries the EXACT same mode,
    crew, memory scope, agent, and model as its source -- upstream's own
    words: "forks into a child of the same memory mode." Only session
    and thread identity are new."""
    life = _life(tmp_path / "s.db")
    source = life.create(
        TENANT, OWNER, "Original chat", "companion-x-default", MODEL,
        mode="incognito", crew_id="redteam-crew", memory_scope="redteam",
    )
    forked = life.fork(TENANT, OWNER, source.session_id)
    assert forked.session_id != source.session_id
    assert forked.thread_id != source.thread_id
    assert forked.mode == "incognito"
    assert forked.crew_id == "redteam-crew"
    assert forked.memory_scope == "redteam"
    assert forked.agent_id == source.agent_id
    assert forked.model == source.model
    assert forked.title == "Original chat (fork)"
    # Both are independently listable and gettable -- a real second row,
    # not an alias.
    assert life.get(TENANT, OWNER, forked.session_id).session_id == forked.session_id
    assert life.get(TENANT, OWNER, source.session_id).session_id == source.session_id


def test_fork_is_owner_scoped(tmp_path: Path) -> None:
    life = _life(tmp_path / "s.db")
    source = life.create(TENANT, OWNER, "t", "companion-x-default", MODEL)
    with pytest.raises((SessionNotFoundError, SessionConflictError)):
        life.fork(TENANT, "owner-b", source.session_id)


def test_legacy_table_migrates_and_defaults_are_readable(tmp_path: Path) -> None:
    path = tmp_path / "legacy.db"
    sql = _sql(path)
    sql.execute(_LEGACY_SCHEMA)
    now = datetime.now(timezone.utc).isoformat()
    sql.execute(
        "INSERT INTO companion_sessions (tenant_id, owner_id, session_id, thread_id, "
        "title, agent_id, model, mode, workspace, project, origin, created_at, "
        "updated_at, revision) VALUES (:t, :o, :s, :th, 't', 'a', :m, '', '', '', "
        "'user', :n, :n, 1)",
        {"t": TENANT, "o": OWNER, "s": "legacy-1", "th": "thr", "m": MODEL, "n": now},
    )
    life = SessionLifecycle(SQLSessionStore(sql))  # __init__ runs migration
    record = life.get(TENANT, OWNER, "legacy-1")
    assert record.crew_id == "" and record.memory_scope == ""
    # Migrated column is writable through the CAS set-model path.
    updated = life.set_model(TENANT, OWNER, "legacy-1", "ollama/llama3", record.revision)
    assert updated.model == "ollama/llama3" and updated.revision == 2


def test_set_model_validates_and_is_revision_fenced(tmp_path: Path) -> None:
    life = _life(tmp_path / "s.db")
    created = life.create(TENANT, OWNER, "t", "companion-x-default", MODEL)
    updated = life.set_model(TENANT, OWNER, created.session_id, "openrouter/x/y", created.revision)
    assert updated.model == "openrouter/x/y" and updated.revision == 2
    with pytest.raises(SessionConflictError):
        life.set_model(TENANT, OWNER, created.session_id, MODEL, created.revision)


@pytest.mark.parametrize("bad", ["", "   ", "openrouter/"])
def test_set_model_rejects_empty_or_unresolvable(tmp_path: Path, bad: str) -> None:
    life = _life(tmp_path / "s.db")
    created = life.create(TENANT, OWNER, "t", "companion-x-default", MODEL)
    with pytest.raises(SessionBindingRejectedError):
        life.set_model(TENANT, OWNER, created.session_id, bad, created.revision)
    assert life.get(TENANT, OWNER, created.session_id).model == MODEL


def test_set_active_checkpoint_pins_and_is_revision_fenced(tmp_path: Path) -> None:
    life = _life(tmp_path / "s.db")
    created = life.create(TENANT, OWNER, "t", "companion-x-default", MODEL)
    assert created.active_checkpoint_id is None
    updated = life.set_active_checkpoint(
        TENANT, OWNER, created.session_id, "ckpt-abc", created.revision,
    )
    assert updated.active_checkpoint_id == "ckpt-abc" and updated.revision == 2
    with pytest.raises(SessionConflictError):
        life.set_active_checkpoint(TENANT, OWNER, created.session_id, "ckpt-xyz", created.revision)


def test_set_active_checkpoint_can_clear_the_pointer(tmp_path: Path) -> None:
    life = _life(tmp_path / "s.db")
    created = life.create(TENANT, OWNER, "t", "companion-x-default", MODEL)
    pinned = life.set_active_checkpoint(TENANT, OWNER, created.session_id, "ckpt-abc", created.revision)
    cleared = life.set_active_checkpoint(TENANT, OWNER, created.session_id, None, pinned.revision)
    assert cleared.active_checkpoint_id is None and cleared.revision == 3


def test_rebind_materializes_crew_scope_and_model(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    import factory.devtools.interface as devtools
    monkeypatch.setattr(devtools, "validate_project", lambda *args: args[-1])
    life = _life(tmp_path / "s.db")
    created = life.create(TENANT, OWNER, "t", "companion-x-default", MODEL)
    bound = life.rebind(
        TENANT, OWNER, created.session_id, "new-crew", "new-scope",
        "companion-x-default", "openrouter/a/b", created.revision,
        project="/validated/project", workspace="workspace-a",
    )
    assert bound.crew_id == "new-crew" and bound.memory_scope == "new-scope"
    assert bound.model == "openrouter/a/b" and bound.revision == 2
    assert bound.agent_id == "companion-x-default"
    assert (bound.project, bound.workspace) == ("/validated/project", "workspace-a")


def test_rebind_owner_isolation_and_stale_cas(tmp_path: Path) -> None:
    life = _life(tmp_path / "s.db")
    created = life.create(TENANT, OWNER, "t", "companion-x-default", MODEL)
    with pytest.raises(SessionNotFoundError):
        life.rebind(TENANT, "owner-b", created.session_id, "c", "s",
                    "companion-x-default", MODEL, 1)
    life.rebind(TENANT, OWNER, created.session_id, "c", "s",
                "companion-x-default", MODEL, created.revision)
    with pytest.raises(SessionConflictError):
        life.rebind(TENANT, OWNER, created.session_id, "c2", "s2",
                    "companion-x-default", MODEL, created.revision)


def test_binding_survives_restart(tmp_path: Path) -> None:
    path = tmp_path / "restart.db"
    created = _life(path).create(
        TENANT, OWNER, "t", "companion-x-default", MODEL,
        crew_id="persist-crew", memory_scope="persist",
    )
    reopened = _life(path).get(TENANT, OWNER, created.session_id)
    assert reopened.crew_id == "persist-crew" and reopened.memory_scope == "persist"


def test_set_model_tool_reports_typed_binding_rejection(tmp_path: Path) -> None:
    sql = _sql(tmp_path / "tool.db")
    runtime = SessionRuntime(SessionLifecycle(SQLSessionStore(sql)))
    tools = create_tool_catalog(runtime).tool_map()
    env = {"tenant_id": TENANT, "principal_id": OWNER}
    created = tools["session_create"].fn(
        title="t", agent_id="companion-x-default", model=MODEL, envelope=env,
    ).data.session
    rejected = tools["session_set_model"].fn(
        session_id=created.session_id, model="   ",
        expected_revision=created.revision, envelope=env,
    )
    assert rejected.ok is False and rejected.error == "session_binding_rejected"
    ok = tools["session_rebind"].fn(
        session_id=created.session_id, agent_id="companion-x-default",
        model="ollama/llama3", crew_id="crew-x", memory_scope="scope-x",
        expected_revision=created.revision, envelope=env,
    )
    assert ok.ok is True and ok.data.session.crew_id == "crew-x"


@settings(max_examples=40, deadline=None)
@given(
    scope_a=st.from_regex(r"[a-z0-9][a-z0-9_-]{0,20}", fullmatch=True),
    scope_b=st.from_regex(r"[a-z0-9][a-z0-9_-]{0,20}", fullmatch=True),
)
def test_concurrent_rebind_has_single_cas_winner(
    tmp_path_factory, scope_a: str, scope_b: str,
) -> None:
    path = tmp_path_factory.mktemp("cas") / "s.db"
    life = _life(path)
    created = life.create(TENANT, OWNER, "t", "companion-x-default", MODEL)
    first = life.rebind(
        TENANT, OWNER, created.session_id, "c", scope_a,
        "companion-x-default", MODEL, created.revision,
    )
    assert first.memory_scope == scope_a and first.revision == created.revision + 1
    with pytest.raises(SessionConflictError):
        life.rebind(
            TENANT, OWNER, created.session_id, "c", scope_b,
            "companion-x-default", MODEL, created.revision,
        )
