"""Owner login-shell resolution for PTY sessions."""
from __future__ import annotations

import os
import shutil
from pathlib import Path


class ShellUnavailable(ValueError):
    pass


def resolve_shell(requested: str | None = None) -> str:
    """Resolve an explicit shell or the owner's configured login shell."""
    candidate = requested or os.environ.get("SHELL") or "/bin/bash"
    resolved = shutil.which(candidate) if Path(candidate).name == candidate else candidate
    if not resolved:
        raise ShellUnavailable("terminal shell unavailable")
    path = Path(resolved).expanduser().resolve(strict=True)
    if not path.is_file() or not os.access(path, os.X_OK):
        raise ShellUnavailable("terminal shell unavailable")
    return str(path)


def list_available_shells() -> list[str]:
    """Return executable shells declared by the host, plus the current default."""
    values: set[str] = set()
    shells = Path("/etc/shells")
    if shells.exists():
        for line in shells.read_text(encoding="utf-8", errors="replace").splitlines():
            value = line.strip()
            if value and not value.startswith("#"):
                try:
                    values.add(resolve_shell(value))
                except (OSError, ShellUnavailable):
                    pass
    try:
        values.add(resolve_shell())
    except (OSError, ShellUnavailable):
        pass
    return sorted(values)


__all__ = ["ShellUnavailable", "list_available_shells", "resolve_shell"]
