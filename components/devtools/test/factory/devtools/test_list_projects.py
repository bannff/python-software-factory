"""The picker must only be offered projects `bind_project` would admit."""
from __future__ import annotations

import asyncio
import os
from pathlib import Path

from factory.devtools.interface import list_projects, validate_project
from factory.devtools.server import create_tool_catalog


def _workspace(tmp_path: Path, monkeypatch) -> Path:
    root = tmp_path / "a" / "b" / "work"
    root.mkdir(parents=True)
    (root / "py").mkdir()
    (root / "py" / "pyproject.toml").write_text("")
    (root / "js").mkdir()
    (root / "js" / "package.json").write_text("{}")
    (root / "git").mkdir()
    (root / "git" / ".git").mkdir()
    (root / "plain").mkdir()
    (root / "file.txt").write_text("")
    monkeypatch.setenv("COMPANION_X_PROJECT_ALLOWED_ROOTS", str(root))
    return root.resolve()


def test_lists_marked_children_and_skips_roots_and_unmarked_dirs(
    tmp_path: Path, monkeypatch,
) -> None:
    root = _workspace(tmp_path, monkeypatch)

    assert list_projects() == [str(root / n) for n in ("git", "js", "py")]


def test_every_listed_project_is_admitted_by_validate_project(
    tmp_path: Path, monkeypatch,
) -> None:
    _workspace(tmp_path, monkeypatch)

    for project in list_projects():
        assert validate_project("t", "o", "s", project) == project


def test_a_root_that_is_itself_a_project_is_listed(tmp_path: Path, monkeypatch) -> None:
    root = _workspace(tmp_path, monkeypatch)
    (root / "pyproject.toml").write_text("")

    assert str(root) in list_projects()


def test_roots_joined_by_pathsep_are_deduplicated(tmp_path: Path, monkeypatch) -> None:
    root = _workspace(tmp_path, monkeypatch)
    monkeypatch.setenv("COMPANION_X_PROJECT_ALLOWED_ROOTS", f"{root}{os.pathsep}{root}")

    assert len(list_projects()) == 3


def test_the_mcp_tool_returns_the_interface_projects(tmp_path: Path, monkeypatch) -> None:
    _workspace(tmp_path, monkeypatch)

    class Runtime:
        pass

    tool = asyncio.run(create_tool_catalog(Runtime()).get_tool("devtools_list_projects"))
    result = tool.fn()

    assert result.ok is True
    assert result.data.projects == list_projects()
