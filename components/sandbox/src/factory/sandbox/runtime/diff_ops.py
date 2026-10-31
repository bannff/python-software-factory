"""Agnostic change detection inside a sandbox environment via git.

Git is language- and framework-neutral, so ``git status`` gives a uniform
"what did the agent touch" signal for any code target. Degrades gracefully when
the path is not a git repository (returns ``is_git_repo=False`` rather than
raising), so non-git targets simply report no changes.
"""
from __future__ import annotations

import shlex
from typing import Any, Awaitable, Callable

ExecFn = Callable[[str, str, int], Awaitable[dict[str, Any]]]


def _parse_porcelain(text: str) -> list[dict[str, str]]:
    """Parse ``git status --porcelain`` lines into ``{status, path}`` records."""
    files: list[dict[str, str]] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        status = line[:2].strip() or "?"
        path = line[3:].strip()
        if path:
            files.append({"status": status, "path": path})
    return files


async def git_diff(execute: ExecFn, env_id: str, path: str) -> dict[str, Any]:
    """Return changed files (tracked + untracked) and a diff stat for ``path``."""
    quoted = shlex.quote(path)
    probe = await execute(
        env_id, f"git -C {quoted} rev-parse --is-inside-work-tree", 30,
    )
    if probe.get("exit_code", 1) != 0:
        return {"is_git_repo": False, "path": path, "files": [], "stat": ""}

    status = await execute(env_id, f"git -C {quoted} status --porcelain", 30)
    stat = await execute(env_id, f"git -C {quoted} diff --stat", 30)
    return {
        "is_git_repo": True,
        "path": path,
        "files": _parse_porcelain(status.get("stdout", "")),
        "stat": stat.get("stdout", ""),
    }
