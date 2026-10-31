"""Focused tests for rename-aware Guardian pull-request LOC ratcheting."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from factory.foreman.guardian import check_file_sizes

_GIT_ENV = {
    **os.environ,
    "GIT_AUTHOR_NAME": "Guardian Test",
    "GIT_AUTHOR_EMAIL": "guardian@example.test",
    "GIT_COMMITTER_NAME": "Guardian Test",
    "GIT_COMMITTER_EMAIL": "guardian@example.test",
}


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=root, env=_GIT_ENV, capture_output=True, text=True, check=True
    )
    return result.stdout.strip()


def _write(root: Path, relative: str, lines: int) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("line\n" * lines)


def _commit(root: Path, message: str) -> str:
    _git(root, "add", "-A")
    _git(root, "commit", "-m", message)
    return _git(root, "rev-parse", "HEAD")


@pytest.fixture
def repo(tmp_path: Path) -> tuple[Path, str]:
    _git(tmp_path, "init", "-b", "main")
    _write(tmp_path, "components/demo/src/factory/demo/legacy.py", 210)
    _write(tmp_path, "components/demo/src/factory/demo/boundary.py", 200)
    _write(tmp_path, "components/demo/src/factory/demo/deleted.py", 210)
    _write(tmp_path, "bases/demo/src/factory/demo/rename_me.py", 210)
    return tmp_path, _commit(tmp_path, "base")


def _ratchet(root: Path, base: str) -> dict:
    return check_file_sizes(root, mode="ratchet", base_sha=base)


def test_strict_whole_tree_remains_default(repo: tuple[Path, str]) -> None:
    root, _ = repo
    result = check_file_sizes(root)
    assert result["mode"] == "strict"
    assert result["passed"] is False
    assert result["total_violations"] == 3


def test_new_oversized_file_fails(repo: tuple[Path, str]) -> None:
    root, base = repo
    _write(root, "components/demo/src/factory/demo/new.py", 201)
    _commit(root, "new oversized")
    violation = _ratchet(root, base)["violations"][0]
    assert violation["reason"] == "new_file_over_limit"
    assert violation["base_lines"] is None


def test_newly_oversized_file_fails(repo: tuple[Path, str]) -> None:
    root, base = repo
    _write(root, "components/demo/src/factory/demo/boundary.py", 201)
    _commit(root, "cross boundary")
    violation = _ratchet(root, base)["violations"][0]
    assert (violation["base_lines"], violation["lines"]) == (200, 201)
    assert violation["reason"] == "newly_over_limit"


def test_legacy_oversized_growth_fails(repo: tuple[Path, str]) -> None:
    root, base = repo
    _write(root, "components/demo/src/factory/demo/legacy.py", 211)
    _commit(root, "grow legacy")
    violation = _ratchet(root, base)["violations"][0]
    assert (violation["base_lines"], violation["lines"]) == (210, 211)
    assert violation["reason"] == "legacy_file_grew"


def test_decrease_delete_unchanged_and_true_rename_pass(repo: tuple[Path, str]) -> None:
    root, base = repo
    _write(root, "components/demo/src/factory/demo/legacy.py", 205)
    (root / "components/demo/src/factory/demo/deleted.py").unlink()
    source = root / "bases/demo/src/factory/demo/rename_me.py"
    source.rename(source.with_name("renamed.py"))
    _write(root, "components/demo/src/factory/demo/small.py", 200)
    _commit(root, "allowed ratchet changes")
    result = _ratchet(root, base)
    assert result["passed"] is True
    assert result["total_violations"] == 0


@pytest.mark.parametrize("base_sha", [None, "", "not-a-sha", "f" * 40])
def test_missing_or_invalid_base_fails_closed(
    repo: tuple[Path, str], base_sha: str | None
) -> None:
    root, _ = repo
    result = check_file_sizes(root, mode="ratchet", base_sha=base_sha)
    assert result["passed"] is False
    assert result["error"]
