"""Fail-closed local path confinement for the Dataset CAN terminal."""
from __future__ import annotations

import os
from pathlib import Path


def secure_storage_root(value: Path) -> Path:
    """Create a lexical storage root without following symlink components."""
    root = _absolute(value)
    _reject_symlinks(root)
    root.mkdir(parents=True, exist_ok=True)
    _reject_symlinks(root)
    return root.resolve()


def checked_output_path(root: Path, value: Path) -> Path:
    """Require an output path to remain under root with no symlink component."""
    base = _absolute(root)
    candidate = _absolute(value)
    try:
        candidate.relative_to(base)
    except ValueError as exc:
        raise ValueError("CAN terminal output escaped storage root") from exc
    _reject_symlinks(candidate)
    return candidate


def checked_source_path(value: Path) -> Path:
    """Require an existing source path whose lexical components are not symlinks."""
    candidate = _absolute(value)
    _reject_symlinks(candidate)
    if not candidate.exists():
        raise ValueError(f"CAN terminal source not found: {candidate}")
    return candidate.resolve()


def select_storage_root(registered: Path, requested: str | None) -> Path:
    """Confine an MCP per-call storage root to the server-configured root."""
    base = secure_storage_root(registered)
    if requested is None:
        return base
    selected = _absolute(Path(requested))
    try:
        selected.relative_to(base)
    except ValueError as exc:
        raise ValueError("storage_root must be within the configured Dataset root") from exc
    return secure_storage_root(selected)


def _absolute(value: Path) -> Path:
    expanded = value.expanduser()
    if ".." in expanded.parts:
        raise ValueError("CAN terminal path traversal is forbidden")
    return Path(os.path.abspath(expanded))


def _reject_symlinks(value: Path) -> None:
    current = Path(value.anchor)
    for part in value.parts[1:]:
        current /= part
        if current.is_symlink():
            system_alias = current.parent == Path("/") and current.lstat().st_uid == 0
            if not system_alias:
                raise ValueError(f"CAN terminal path contains a symlink: {current}")
        if not current.exists():
            break


__all__ = [
    "checked_output_path", "checked_source_path", "secure_storage_root",
    "select_storage_root",
]
