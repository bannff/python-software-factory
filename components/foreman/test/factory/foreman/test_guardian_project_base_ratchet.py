"""Focused tests for semantic project-base PR ratcheting."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

import factory.foreman.guardian as guardian
from factory.foreman.guardian import check_projects_have_base

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


def _project(root: Path, name: str, *, has_base: bool) -> None:
    path = root / "projects" / name / "pyproject.toml"
    path.parent.mkdir(parents=True, exist_ok=True)
    source = "../../bases/api/src/factory/api" if has_base else "../../components/ui/src/factory/ui"
    path.write_text(
        f'''[project]\nname = "{name}"\ndescription = "../../bases/text-is-not-wiring"\n\n'''
        f'''[tool.polylith.bricks]\n"{source}" = "factory/{Path(source).name}"\n'''
    )


def _commit(root: Path, message: str) -> str:
    _git(root, "add", "-A")
    _git(root, "commit", "-m", message)
    return _git(root, "rev-parse", "HEAD")


@pytest.fixture
def repo(tmp_path: Path) -> tuple[Path, str]:
    _git(tmp_path, "init", "-b", "main")
    _project(tmp_path, "legacy", has_base=False)
    _project(tmp_path, "compliant", has_base=True)
    return tmp_path, _commit(tmp_path, "base")


def _ratchet(root: Path, base: str) -> dict:
    return check_projects_have_base(root, mode="ratchet", base_sha=base)


def test_strict_default_parses_brick_sources_and_blocks_all_debt(
    repo: tuple[Path, str],
) -> None:
    root, _ = repo
    result = check_projects_have_base(root)
    assert result["mode"] == "strict"
    assert result["passed"] is False
    assert [item["path"] for item in result["violations"]] == [
        "projects/legacy/pyproject.toml"
    ]


def test_unchanged_legacy_passes_but_is_reported(repo: tuple[Path, str]) -> None:
    root, base = repo
    result = _ratchet(root, base)
    assert result["passed"] is True
    assert result["violations"] == []
    assert [item["path"] for item in result["legacy_violations"]] == [
        "projects/legacy/pyproject.toml"
    ]


def test_new_and_regressed_missing_base_projects_block(repo: tuple[Path, str]) -> None:
    root, base = repo
    _project(root, "new_project", has_base=False)
    _project(root, "compliant", has_base=False)
    _commit(root, "introduce debt")
    result = _ratchet(root, base)
    assert result["passed"] is False
    assert {item["path"] for item in result["violations"]} == {
        "projects/compliant/pyproject.toml",
        "projects/new_project/pyproject.toml",
    }


def test_renamed_legacy_violation_blocks_as_new_identity(repo: tuple[Path, str]) -> None:
    root, base = repo
    (root / "projects" / "legacy").rename(root / "projects" / "renamed")
    _commit(root, "rename debt")
    result = _ratchet(root, base)
    assert [item["path"] for item in result["violations"]] == [
        "projects/renamed/pyproject.toml"
    ]
    assert [item["path"] for item in result["resolved_violations"]] == [
        "projects/legacy/pyproject.toml"
    ]


def test_resolved_debt_is_reported_without_blocking(repo: tuple[Path, str]) -> None:
    root, base = repo
    _project(root, "legacy", has_base=True)
    _commit(root, "resolve debt")
    result = _ratchet(root, base)
    assert result["passed"] is True
    assert result["legacy_violations"] == []
    assert [item["path"] for item in result["resolved_violations"]] == [
        "projects/legacy/pyproject.toml"
    ]


@pytest.mark.parametrize("base_sha", [None, "", "not-a-sha", "f" * 40])
def test_missing_invalid_or_unresolvable_base_fails_closed(
    repo: tuple[Path, str], base_sha: str | None
) -> None:
    root, _ = repo
    result = check_projects_have_base(root, mode="ratchet", base_sha=base_sha)
    assert result["passed"] is False
    assert result["error"]


@pytest.mark.parametrize("bad_content", [b"not = [", b"\xff", b'tool = "wrong"\n'])
def test_unreadable_or_invalid_base_toml_fails_closed(
    tmp_path: Path, bad_content: bytes
) -> None:
    _git(tmp_path, "init", "-b", "main")
    path = tmp_path / "projects" / "broken" / "pyproject.toml"
    path.parent.mkdir(parents=True)
    path.write_bytes(bad_content)
    base = _commit(tmp_path, "bad base")
    _project(tmp_path, "broken", has_base=True)
    _commit(tmp_path, "valid head")
    result = _ratchet(tmp_path, base)
    assert result["passed"] is False
    assert result["error"]


def test_run_all_checks_threads_ratchet_mode_to_project_check(
    repo: tuple[Path, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    root, base = repo
    passing = lambda *_args, **_kwargs: {"check": "stub", "passed": True}
    monkeypatch.setattr(guardian, "check_import_integrity", passing)
    monkeypatch.setattr(guardian, "check_branch_naming", passing)
    monkeypatch.setattr(guardian, "check_file_sizes", passing)
    monkeypatch.setattr(guardian, "check_bricks_index", passing)

    result = guardian.run_all_checks(root, file_size_mode="ratchet", base_sha=base)
    project_check = result["checks"][-2]
    assert result["passed"] is True
    assert project_check["mode"] == "ratchet"
    assert project_check["legacy_violations"]
