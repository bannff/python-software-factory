"""Branch-name governance, including detached GitHub Actions checkouts."""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from typing import Any, Mapping

_BRANCH_RE = re.compile(
    r"^(?:"
    r"(?:feat|fix|chore)/(?:\d+|python-factory-[a-z0-9]+(?:\.[a-z0-9]+)*)-"
    r"[a-z0-9][a-z0-9._-]*"
    r"|dependabot/[a-z0-9_]+/[A-Za-z0-9][A-Za-z0-9._/-]*"
    r")$"
)


def _github_branch(environ: Mapping[str, str]) -> str:
    """Resolve a detached checkout only from GitHub's branch-name fields."""
    head_ref = environ.get("GITHUB_HEAD_REF", "")
    return head_ref if head_ref else environ.get("GITHUB_REF_NAME", "")


def check_branch_naming(
    workspace_root: Path | None = None,
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Validate the real branch, or trusted GitHub metadata for literal HEAD."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
            cwd=workspace_root,
        )
        if result.returncode != 0:
            return {"check": "branch_naming", "passed": True, "skipped": "not a git repo"}

        git_branch = result.stdout.strip()
        branch = _github_branch(environ or os.environ) if git_branch == "HEAD" else git_branch
        source = "github_env" if git_branch == "HEAD" else "git"
        if branch in ("main", "master"):
            return {"check": "branch_naming", "passed": True, "branch": branch, "source": source}
        if branch != "HEAD" and _BRANCH_RE.fullmatch(branch):
            return {"check": "branch_naming", "passed": True, "branch": branch, "source": source}
        return {
            "check": "branch_naming",
            "passed": False,
            "branch": branch or git_branch,
            "source": source,
            "error": (
                f"Branch '{branch or git_branch}' doesn't match pattern: "
                "feat/<issue>-*, fix/<issue>-*, chore/<issue>-*"
            ),
        }
    except Exception as exc:
        return {"check": "branch_naming", "passed": False, "error": str(exc)}
