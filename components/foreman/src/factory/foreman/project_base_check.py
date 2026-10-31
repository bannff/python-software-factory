"""Strict and pull-request-ratcheted project base-brick checks."""

from __future__ import annotations

import posixpath
import re
import subprocess
import tomllib
from pathlib import Path
from typing import Any

_SHA_RE = re.compile(r"[0-9a-fA-F]{7,64}")
_ERROR = "No base brick wired — project has no entry point"


def _git(root: Path, args: list[str], *, text: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], capture_output=True, text=text, check=False, cwd=root
    )


def _project_name(path: str) -> str:
    parts = Path(path).parts
    return parts[1] if len(parts) > 1 else path


def _base_sources(project_path: str, content: bytes) -> tuple[str, ...]:
    data = tomllib.loads(content.decode("utf-8"))
    tool = data.get("tool", {})
    if not isinstance(tool, dict):
        raise ValueError("[tool] must be a TOML table")
    polylith = tool.get("polylith", {})
    if not isinstance(polylith, dict):
        raise ValueError("[tool.polylith] must be a TOML table")
    bricks = polylith.get("bricks", {})
    if not isinstance(bricks, dict):
        raise ValueError("[tool.polylith.bricks] must be a TOML table")

    project_dir = posixpath.dirname(project_path)
    sources: list[str] = []
    for source in bricks:
        if not isinstance(source, str) or posixpath.isabs(source):
            continue
        identity = posixpath.normpath(posixpath.join(project_dir, source))
        if identity.startswith("bases/"):
            sources.append(identity)
    return tuple(sorted(sources))


def _violation(path: str) -> dict[str, str]:
    return {"project": _project_name(path), "path": path, "error": _ERROR}


def _head_projects(root: Path) -> dict[str, tuple[str, ...]]:
    projects_dir = root / "projects"
    if not projects_dir.exists():
        return {}
    projects: dict[str, tuple[str, ...]] = {}
    for project_dir in sorted(projects_dir.iterdir()):
        pyproject = project_dir / "pyproject.toml"
        if not pyproject.exists():
            continue
        relative = pyproject.relative_to(root).as_posix()
        projects[relative] = _base_sources(relative, pyproject.read_bytes())
    return projects


def _base_projects(root: Path, base_sha: str) -> dict[str, tuple[str, ...]]:
    listing = _git(root, ["ls-tree", "-r", "-z", "--name-only", base_sha, "--", "projects"], text=False)
    if listing.returncode != 0:
        error = listing.stderr.decode(errors="replace").strip()
        raise ValueError(error or "cannot list projects at base_sha")

    paths = sorted(
        token.decode(errors="surrogateescape")
        for token in listing.stdout.split(b"\0")
        if token and re.fullmatch(rb"projects/[^/]+/pyproject\.toml", token)
    )
    projects: dict[str, tuple[str, ...]] = {}
    for path in paths:
        shown = _git(root, ["show", f"{base_sha}:{path}"], text=False)
        if shown.returncode != 0:
            error = shown.stderr.decode(errors="replace").strip()
            raise ValueError(error or f"cannot read base project: {path}")
        projects[path] = _base_sources(path, shown.stdout)
    return projects


def _failure(mode: str, error: str) -> dict[str, Any]:
    return {
        "check": "project_has_base", "mode": mode, "passed": False,
        "projects_checked": 0, "violations": [], "legacy_violations": [],
        "resolved_violations": [], "error": error,
    }


def _strict(root: Path) -> dict[str, Any]:
    try:
        projects = _head_projects(root)
    except (OSError, UnicodeError, tomllib.TOMLDecodeError, ValueError) as exc:
        return _failure("strict", str(exc))
    violations = [_violation(path) for path, sources in projects.items() if not sources]
    return {
        "check": "project_has_base", "mode": "strict", "passed": not violations,
        "projects_checked": len(projects), "violations": violations,
    }


def _ratchet(root: Path, base_sha: str | None) -> dict[str, Any]:
    if not base_sha:
        return _failure("ratchet", "base_sha is required for ratchet mode")
    if not _SHA_RE.fullmatch(base_sha):
        return _failure("ratchet", "base_sha must be a hexadecimal commit SHA")
    verify = _git(root, ["rev-parse", "--verify", "--quiet", f"{base_sha}^{{commit}}"])
    if verify.returncode != 0:
        return _failure("ratchet", f"base_sha does not resolve: {base_sha}")

    try:
        base_projects = _base_projects(root, base_sha)
        head_projects = _head_projects(root)
    except (OSError, UnicodeError, tomllib.TOMLDecodeError, ValueError) as exc:
        return _failure("ratchet", str(exc))

    base_debt = {path for path, sources in base_projects.items() if not sources}
    head_debt = {path for path, sources in head_projects.items() if not sources}
    blocking = sorted(head_debt - base_debt)
    legacy = sorted(head_debt & base_debt)
    resolved = sorted(base_debt - head_debt)
    return {
        "check": "project_has_base", "mode": "ratchet", "passed": not blocking,
        "projects_checked": len(head_projects), "base_projects_checked": len(base_projects),
        "violations": [_violation(path) for path in blocking],
        "legacy_violations": [_violation(path) for path in legacy],
        "resolved_violations": [_violation(path) for path in resolved],
    }


def check_projects_have_base(
    workspace_root: Path | None = None,
    mode: str = "strict",
    base_sha: str | None = None,
) -> dict[str, Any]:
    """Require project base bricks strictly, or ratchet legacy PR debt by path."""
    root = workspace_root or Path.cwd()
    if mode == "strict":
        return _strict(root)
    if mode == "ratchet":
        return _ratchet(root, base_sha)
    return _failure(mode, f"unknown project-base mode: {mode}")
