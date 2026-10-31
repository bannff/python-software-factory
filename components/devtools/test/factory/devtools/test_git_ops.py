from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from factory.devtools.runtime.git_ops import (
    GitFailed, GitRefused, git_commit, git_diff, git_log, git_push,
    git_stage, git_status,
)
from factory.devtools.runtime.models import ProjectBinding


def _run(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(root), *args], check=True,
        capture_output=True, text=True,
    )


def _repo(tmp_path: Path) -> tuple[Path, ProjectBinding]:
    root = tmp_path / "project"
    root.mkdir()
    _run(root, "init", "-b", "feature/test")
    _run(root, "config", "user.email", "fixture@example.invalid")
    _run(root, "config", "user.name", "Fixture")
    (root / "tracked.txt").write_text("before\n")
    _run(root, "add", "tracked.txt")
    _run(root, "commit", "-m", "initial")
    return root, ProjectBinding(
        tenant_id="tenant", owner_id="owner", session_id="session",
        root=str(root.resolve()),
    )


def test_git_reads_are_bounded_and_external_diff_is_disabled(tmp_path) -> None:
    root, binding = _repo(tmp_path)
    marker = root / "external-ran"
    helper = root / "external-diff"
    helper.write_text(f"#!/bin/sh\ntouch '{marker}'\n")
    helper.chmod(0o755)
    fs_marker = root / "fsmonitor-ran"
    fs_helper = root / "fsmonitor"
    fs_helper.write_text(f"#!/bin/sh\ntouch '{fs_marker}'\n")
    fs_helper.chmod(0o755)
    _run(root, "config", "diff.external", str(helper))
    _run(root, "config", "core.fsmonitor", str(fs_helper))
    (root / "tracked.txt").write_text("after\n")
    status = git_status(binding)
    diff = git_diff(binding, ["tracked.txt"])
    log = git_log(binding, ["tracked.txt"], limit=1)
    assert "tracked.txt" in status.output
    assert "-before" in diff.output and "+after" in diff.output
    assert "initial" in log.output
    assert not marker.exists()
    assert not fs_marker.exists()


def test_stage_requires_explicit_confined_paths(tmp_path) -> None:
    root, binding = _repo(tmp_path)
    (root / "tracked.txt").write_text("changed\n")
    staged = git_stage(binding, ["tracked.txt"])
    assert staged.paths == ("tracked.txt",)
    assert "tracked.txt" in git_diff(binding, ["tracked.txt"], staged=True).output
    for paths in ([], ["."], ["../outside"], [".env"]):
        with pytest.raises((GitRefused, ValueError, PermissionError)):
            git_stage(binding, paths)


def test_commit_preserves_hooks_unless_explicitly_skipped(tmp_path) -> None:
    root, binding = _repo(tmp_path)
    (root / "tracked.txt").write_text("changed\n")
    git_stage(binding, ["tracked.txt"])
    hook = root / ".git" / "hooks" / "pre-commit"
    hook.write_text("#!/bin/sh\nexit 1\n")
    hook.chmod(0o755)
    with pytest.raises(GitFailed):
        git_commit(binding, "must run hook")
    committed = git_commit(binding, "explicit skip", skip_hooks=True)
    assert committed.commit and len(committed.commit) == 40
    assert _run(root, "log", "-1", "--format=%s").stdout.strip() == "explicit skip"


@pytest.mark.parametrize("branch", ["main", "master", "mainline", "trunk", "HEAD", "@"])
def test_push_refuses_protected_and_symbolic_branches(tmp_path, branch) -> None:
    _, binding = _repo(tmp_path)
    with pytest.raises(GitRefused):
        git_push(binding, "origin", branch)


def test_push_requires_checked_out_explicit_branch_and_supports_local_remote(tmp_path) -> None:
    root, binding = _repo(tmp_path)
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "--bare", str(remote)], check=True, capture_output=True)
    _run(root, "remote", "add", "origin", str(remote))
    with pytest.raises(GitRefused, match="checked-out"):
        git_push(binding, "origin", "feature/other")
    pushed = git_push(binding, "origin", "feature/test", set_upstream=True)
    assert pushed.branch == "feature/test"
    assert _run(root, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}").stdout.strip() == "origin/feature/test"
