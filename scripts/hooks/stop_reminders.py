"""Emit a short session-end reminder when the worktree is dirty."""

from __future__ import annotations

import json
import subprocess
import sys


def _run_git(*args: str) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(
            ["git", *args],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return None


def _emit(payload: dict[str, object]) -> None:
    sys.stdout.write(json.dumps(payload))


def main() -> int:
    status = _run_git("status", "--porcelain")
    if status is None or status.returncode != 0 or not status.stdout.strip():
        _emit({"continue": True})
        return 0

    diff = _run_git("diff", "--name-only")
    files = []
    if diff and diff.returncode == 0:
        files = [line for line in diff.stdout.splitlines() if line.strip()]

    changed_count = len(files) or len(status.stdout.splitlines())
    preview = ", ".join(files[:5]) if files else "tracked or untracked files"

    message = (
        f"Worktree still has {changed_count} changed file(s): {preview}. "
        "If this session is complete, run targeted tests, run foreman_guardian_check for code changes, and update docs or brick metadata when interfaces changed."
    )
    _emit({"continue": True, "systemMessage": message})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())