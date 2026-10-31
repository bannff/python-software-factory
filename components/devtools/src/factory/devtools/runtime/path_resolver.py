"""Fail-closed project root and relative path resolution."""
from __future__ import annotations

import os
from pathlib import Path

from .models import ProjectBinding, RelativePath
from .sensitive_policy import ensure_not_sensitive


class PathRefused(ValueError):
    pass


def bind_project(
    tenant_id: str, owner_id: str, session_id: str,
    candidate: str, allowed_roots: tuple[Path, ...],
) -> ProjectBinding:
    raw = Path(candidate)
    if not raw.is_absolute():
        raise PathRefused("project root must be absolute")
    root = raw.resolve(strict=True)
    if not root.is_dir() or root in {Path("/"), Path.home(), Path("/tmp")}:
        raise PathRefused("project root is not admissible")
    if len(root.parts) < 4 or not _within_any(root, allowed_roots):
        raise PathRefused("project root is outside allowed roots")
    if not ((root / ".git").exists() or (root / "pyproject.toml").exists()
            or (root / "package.json").exists()):
        raise PathRefused("project marker is required")
    return ProjectBinding(
        tenant_id=tenant_id, owner_id=owner_id,
        session_id=session_id, root=str(root),
    )


def resolve_path(
    binding: ProjectBinding, relative: str, *,
    expect: str = "any", for_write: bool = False,
) -> Path:
    rel = "" if relative == "." else RelativePath(path=relative).path
    root = Path(binding.root).resolve(strict=True)
    candidate = root if not rel else root.joinpath(rel)
    try:
        resolved = (candidate.parent.resolve(strict=True) / candidate.name
                    if for_write and not candidate.exists()
                    else candidate.resolve(strict=True))
        resolved.relative_to(root)
    except (OSError, ValueError) as exc:
        raise PathRefused("path escapes or cannot be resolved") from exc
    ensure_not_sensitive(root, resolved, for_write=for_write)
    if expect == "file" and not resolved.is_file():
        raise PathRefused("path is not a regular file")
    if expect == "dir" and not resolved.is_dir():
        raise PathRefused("path is not a directory")
    return resolved


def _within_any(path: Path, roots: tuple[Path, ...]) -> bool:
    for raw in roots:
        try:
            path.relative_to(raw.resolve(strict=True))
            return True
        except (OSError, ValueError):
            continue
    return False


def nofollow_flag() -> int:
    return getattr(os, "O_NOFOLLOW", 0)


__all__ = ["PathRefused", "bind_project", "nofollow_flag", "resolve_path"]
