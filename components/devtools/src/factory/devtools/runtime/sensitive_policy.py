"""Sensitive file policy for host-local developer tools."""
from __future__ import annotations

from pathlib import Path

_BLOCKED_PARTS = frozenset({".aws", ".ssh", ".gnupg"})
_BLOCKED_NAMES = frozenset({
    ".env", ".netrc", ".npmrc", ".pypirc", "credentials",
    "credentials.json", "id_rsa", "id_ed25519",
})
_BLOCKED_SUFFIXES = (".pem", ".key", ".p12", ".pfx")


def ensure_not_sensitive(root: Path, path: Path, *, for_write: bool) -> None:
    del for_write
    relative = path.relative_to(root)
    lowered = tuple(part.casefold() for part in relative.parts)
    name = path.name.casefold()
    if any(part in _BLOCKED_PARTS for part in lowered):
        raise PermissionError("sensitive project path is denied")
    if name in _BLOCKED_NAMES or name.startswith(".env.") or name.endswith(_BLOCKED_SUFFIXES):
        raise PermissionError("sensitive project path is denied")
    if ".git" in lowered and lowered[-1] in {"config", "credentials"}:
        raise PermissionError("git trust configuration is denied")


def excluded_dir(name: str) -> bool:
    return name in {
        ".git", ".venv", "node_modules", "dist", "build", "target",
        "__pycache__", ".cache",
    }


__all__ = ["ensure_not_sensitive", "excluded_dir"]
