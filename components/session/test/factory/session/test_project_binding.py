from __future__ import annotations

from pathlib import Path

import pytest

from factory.session.runtime.adapters.sql import SQLSessionStore
from factory.session.runtime.errors import SessionConflictError, SessionProjectRejectedError
from factory.session.runtime.lifecycle import SessionLifecycle
from factory.storage.interface import StorageRuntime


def _runtime(path: Path) -> SessionLifecycle:
    sql = StorageRuntime().get_sql_store("sqlite", db_path=str(path))
    return SessionLifecycle(SQLSessionStore(sql))


def _project(tmp_path: Path, name: str) -> Path:
    root = tmp_path / "projects" / name
    root.mkdir(parents=True)
    (root / "pyproject.toml").write_text("[project]\nname='fixture'\n")
    return root


def test_session_create_and_bind_share_canonical_project_validator(
    tmp_path, monkeypatch,
) -> None:
    allowed = tmp_path / "projects"
    allowed.mkdir()
    monkeypatch.setenv("COMPANION_X_PROJECT_ALLOWED_ROOTS", str(allowed))
    first, second = _project(tmp_path, "one"), _project(tmp_path, "two")
    runtime = _runtime(tmp_path / "session.db")
    created = runtime.create(
        "tenant", "owner", "title", "developer", "model",
        project=str(first),
    )
    assert created.project == str(first.resolve())
    bound = runtime.bind_project(
        "tenant", "owner", created.session_id, str(second), created.revision,
    )
    assert bound.project == str(second.resolve()) and bound.revision == 2
    with pytest.raises(SessionConflictError):
        runtime.bind_project(
            "tenant", "owner", created.session_id, str(first), created.revision,
        )
    assert runtime.store.get("tenant", "other", created.session_id) is None


def test_invalid_and_archived_project_binding_fail_closed(tmp_path, monkeypatch) -> None:
    allowed = tmp_path / "projects"
    allowed.mkdir()
    monkeypatch.setenv("COMPANION_X_PROJECT_ALLOWED_ROOTS", str(allowed))
    project = _project(tmp_path, "valid")
    runtime = _runtime(tmp_path / "session.db")
    with pytest.raises(SessionProjectRejectedError):
        runtime.create("tenant", "owner", "title", "developer", "model", project="relative")
    created = runtime.create("tenant", "owner", "title", "developer", "model")
    archived = runtime.set_archived(
        "tenant", "owner", created.session_id, True, created.revision,
    )
    with pytest.raises(Exception):
        runtime.bind_project(
            "tenant", "owner", archived.session_id, str(project), archived.revision,
        )
