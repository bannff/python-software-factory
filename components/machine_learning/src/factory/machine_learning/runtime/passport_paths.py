"""Shared local path guards for ModelPassport storage and artifacts."""
from __future__ import annotations

from pathlib import Path


def reject_symlink_ancestors(path: Path) -> None:
    """Reject any existing symlink from ``path`` through filesystem root."""
    current = path.expanduser().absolute()
    while True:
        if current.is_symlink():
            raise ValueError("ModelPassport paths must not contain symlink ancestors")
        if current.parent == current:
            return
        current = current.parent


def _require_contained(path: Path, root: Path) -> Path:
    raw_root = root.expanduser().absolute()
    raw_path = path.expanduser().absolute()
    reject_symlink_ancestors(raw_root)
    reject_symlink_ancestors(raw_path)
    try:
        raw_path.relative_to(raw_root)
        raw_path.resolve(strict=True).relative_to(raw_root.resolve(strict=True))
    except (OSError, ValueError) as exc:
        raise ValueError("ModelPassport artifact escapes the supplied storage root") from exc
    return raw_path


def require_contained_file(path: Path, root: Path) -> Path:
    """Return an exact regular file lexically and physically beneath ``root``."""
    raw_path = _require_contained(path, root)
    if not raw_path.is_file() or raw_path.is_symlink():
        raise ValueError("ModelPassport artifact is missing, not a file, or a symlink")
    return raw_path


def require_contained_directory(path: Path, root: Path) -> Path:
    """Return an exact non-symlink directory physically beneath ``root``."""
    raw_path = _require_contained(path, root)
    if not raw_path.is_dir() or raw_path.is_symlink():
        raise ValueError("ModelPassport artifact is missing, not a directory, or a symlink")
    return raw_path


__all__ = [
    "reject_symlink_ancestors", "require_contained_directory",
    "require_contained_file",
]
