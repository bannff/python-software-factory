"""Focused tests for Guardian branch handling in detached CI checkouts."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from factory.foreman.guardian import check_branch_naming

_GIT_ENV = {
    **os.environ,
    "GIT_AUTHOR_NAME": "Guardian Test",
    "GIT_AUTHOR_EMAIL": "guardian@example.test",
    "GIT_COMMITTER_NAME": "Guardian Test",
    "GIT_COMMITTER_EMAIL": "guardian@example.test",
}


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=root, env=_GIT_ENV, capture_output=True, text=True, check=True
    ).stdout.strip()


@pytest.fixture
def repo(tmp_path: Path) -> tuple[Path, str]:
    _git(tmp_path, "init", "-b", "main")
    (tmp_path / "seed").write_text("seed")
    _git(tmp_path, "add", "seed")
    _git(tmp_path, "commit", "-m", "seed")
    sha = _git(tmp_path, "rev-parse", "HEAD")
    return tmp_path, sha


def test_real_branch_is_never_overridden(repo: tuple[Path, str]) -> None:
    root, _ = repo
    _git(root, "checkout", "-b", "fix/python-factory-hfyjj.1-guardian")
    result = check_branch_naming(
        root, {"GITHUB_HEAD_REF": "malicious branch", "GITHUB_REF_NAME": "HEAD"}
    )
    assert result["passed"] is True
    assert result["branch"] == "fix/python-factory-hfyjj.1-guardian"
    assert result["source"] == "git"


def test_invalid_real_branch_is_not_rescued_by_env(repo: tuple[Path, str]) -> None:
    root, _ = repo
    _git(root, "checkout", "-b", "feature/not-approved")
    result = check_branch_naming(root, {"GITHUB_HEAD_REF": "fix/123-valid"})
    assert result["passed"] is False
    assert result["branch"] == "feature/not-approved"


def test_detached_head_prefers_github_head_ref(repo: tuple[Path, str]) -> None:
    root, sha = repo
    _git(root, "checkout", "--detach", sha)
    result = check_branch_naming(
        root,
        {"GITHUB_HEAD_REF": "feat/123-source", "GITHUB_REF_NAME": "fix/456-fallback"},
    )
    assert result["passed"] is True
    assert result["branch"] == "feat/123-source"
    assert result["source"] == "github_env"


def test_detached_head_falls_back_to_ref_name(repo: tuple[Path, str]) -> None:
    root, sha = repo
    _git(root, "checkout", "--detach", sha)
    result = check_branch_naming(
        root, {"GITHUB_HEAD_REF": "", "GITHUB_REF_NAME": "chore/python-factory-abc-cleanup"}
    )
    assert result["passed"] is True
    assert result["branch"] == "chore/python-factory-abc-cleanup"


def test_dependabot_branch_is_allowed(repo: tuple[Path, str]) -> None:
    root, _ = repo
    branch = "dependabot/uv/uv-12e367e9a9"
    _git(root, "checkout", "-b", branch)
    result = check_branch_naming(root, {"GITHUB_HEAD_REF": branch})
    assert result["passed"] is True
    assert result["branch"] == branch


@pytest.mark.parametrize(
    "candidate",
    [
        "HEAD",
        "refs/pull/1/merge",
        "feat/123-ok\nbad",
        "fix/123-$(touch-pwned)",
        " feat/123-leading-space",
        "",
    ],
)
def test_detached_head_rejects_missing_or_malicious_names(
    repo: tuple[Path, str], candidate: str
) -> None:
    root, sha = repo
    _git(root, "checkout", "--detach", sha)
    result = check_branch_naming(root, {"GITHUB_HEAD_REF": candidate})
    assert result["passed"] is False
