"""Confined git reads and explicitly gated mutation primitives."""
from __future__ import annotations

import re
from pathlib import Path

from .git_process import GitFailed, GitRefused, run_git
from .models import GitResult, ProjectBinding, RelativePath
from .path_resolver import resolve_path

_PROTECTED = {"main", "master", "mainline", "trunk"}
_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,127}$")
_REMOTE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


def git_status(binding: ProjectBinding) -> GitResult:
    output, truncated, _ = run_git(binding, ["status", "--porcelain=v1", "--untracked-files=normal"])
    return GitResult(operation="status", output=output, truncated=truncated)


def git_diff(
    binding: ProjectBinding, paths: list[str], *, staged: bool = False,
) -> GitResult:
    confined = _paths(binding, paths, allow_missing=True)
    args = ["diff", "--no-ext-diff", "--no-textconv", "--unified=3"]
    if staged:
        args.append("--cached")
    output, truncated, _ = run_git(binding, [*args, "--", *confined])
    return GitResult(
        operation="diff_staged" if staged else "diff",
        output=output, paths=confined, truncated=truncated,
    )


def git_log(
    binding: ProjectBinding, paths: list[str] | None = None, *, limit: int = 20,
) -> GitResult:
    if not 1 <= limit <= 100:
        raise GitRefused("git log limit is outside bounds")
    confined = _paths(binding, paths or [], allow_missing=True) if paths else ()
    args = ["log", "--no-decorate", f"--max-count={limit}", "--format=%H%x09%aI%x09%s"]
    if confined:
        args.extend(["--", *confined])
    output, truncated, _ = run_git(binding, args)
    return GitResult(operation="log", output=output, paths=confined, truncated=truncated)


def git_stage(binding: ProjectBinding, paths: list[str]) -> GitResult:
    confined = _paths(binding, paths, allow_missing=True)
    run_git(binding, ["add", "--", *confined])
    return GitResult(operation="stage", output="", paths=confined)


def git_commit(
    binding: ProjectBinding, message: str, *, skip_hooks: bool = False,
) -> GitResult:
    if not 1 <= len(message.strip()) <= 1000 or any(ord(c) < 32 and c not in "\n\t" for c in message):
        raise GitRefused("commit message is outside bounds")
    _, _, staged = run_git(binding, ["diff", "--cached", "--quiet"], allowed={0, 1})
    if staged == 0:
        raise GitRefused("commit requires staged changes")
    args = ["commit", "-m", message]
    if skip_hooks:
        args.append("--no-verify")
    output, truncated, _ = run_git(binding, args, timeout=120)
    commit, _, _ = run_git(binding, ["rev-parse", "HEAD"])
    return GitResult(
        operation="commit", output=output, commit=commit.strip(), truncated=truncated,
    )


def git_push(
    binding: ProjectBinding, remote: str, branch: str, *, set_upstream: bool = False,
) -> GitResult:
    if not _REMOTE.fullmatch(remote) or not _NAME.fullmatch(branch):
        raise GitRefused("remote or branch is invalid")
    if branch.casefold() in _PROTECTED or branch in {"HEAD", "@"} or "*" in branch:
        raise GitRefused("protected or symbolic branch cannot be pushed")
    current, _, _ = run_git(binding, ["branch", "--show-current"])
    if current.strip() != branch:
        raise GitRefused("push branch must be the checked-out branch")
    args = ["push"]
    if set_upstream:
        args.append("-u")
    output, truncated, _ = run_git(binding, [*args, remote, branch], timeout=120)
    return GitResult(
        operation="push", output=output, branch=branch, truncated=truncated,
    )


def _paths(
    binding: ProjectBinding, paths: list[str], *, allow_missing: bool,
) -> tuple[str, ...]:
    if not 1 <= len(paths) <= 64:
        raise GitRefused("explicit git paths are required")
    values = []
    root = Path(binding.root).resolve(strict=True)
    for raw in paths:
        if raw == ".":
            raise GitRefused("project-wide staging is not allowed")
        relative = RelativePath(path=raw).path
        if relative.startswith("-"):
            raise GitRefused("git path cannot be option-shaped")
        resolved = resolve_path(binding, relative, for_write=allow_missing)
        values.append(str(resolved.relative_to(root)))
    return tuple(values)


__all__ = [
    "GitFailed", "GitRefused", "git_commit", "git_diff", "git_log", "git_push",
    "git_stage", "git_status",
]
