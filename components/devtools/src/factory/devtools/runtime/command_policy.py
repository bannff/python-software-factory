"""Unrestricted one-shot command resolution for the owner-operated local app.

The former executable/script allowlist and interactive-flag denials are removed
by explicit owner ruling (2026-09-14). This policy now checks only transport
integrity and resolves the requested executable. Project-root cwd confinement,
output redaction/caps, timeout, cancellation, and process-group teardown remain
owned by their existing devtools layers.
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path


class CommandRefused(ValueError):
    pass


def resolve_command(root: Path, argv: list[str]) -> tuple[str, tuple[str, ...]]:
    """Resolve any requested executable without an executable/argument allowlist."""
    if not 1 <= len(argv) <= 64:
        raise CommandRefused("command argument count is outside bounds")
    if sum(len(value) for value in argv) > 8192:
        raise CommandRefused("command arguments exceed size limit")
    for value in argv:
        if not value or "\x00" in value or any(ord(char) < 32 for char in value):
            raise CommandRefused("command contains invalid characters")
    name = argv[0]
    resolved = shutil.which(name, path=os.environ.get("PATH", ""))
    if not resolved:
        raise CommandRefused("executable is unavailable")
    selected = Path(resolved).absolute()
    try:
        executable = selected.resolve(strict=True)
    except OSError as exc:
        raise CommandRefused("executable is unavailable") from exc
    if not executable.is_file() or not os.access(executable, os.X_OK):
        raise CommandRefused("executable is not executable")
    return str(selected), tuple(argv)


def minimal_environment() -> dict[str, str]:
    """Preserve the existing secret-minimizing environment for one-shot commands."""
    keep = ("PATH", "VIRTUAL_ENV", "LANG", "LC_ALL", "TMPDIR")
    env = {key: os.environ[key] for key in keep if os.environ.get(key)}
    env.update({"CI": "1", "NO_COLOR": "1", "PYTHONUTF8": "1", "PAGER": "cat"})
    return env


__all__ = ["CommandRefused", "minimal_environment", "resolve_command"]
