"""Native CLI protocol adapters for Terminal command completion."""
from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

from .models import TerminalCompletionEntry, TerminalCompletionResult

_SAFE_PATH = "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
# Native completion can consult configured services (for example kubectl's API
# server or Docker's daemon). It is intentionally limited to trusted binaries,
# a minimal environment, read-only completion protocols, and a 0.4s timeout.
_COBRA = frozenset({"docker", "gh", "helm", "kubectl"})
_TOKEN = re.compile(r"^(?:--?[\w.-]*|[\w][\w.+:@-]*)$", re.UNICODE)


def _executable(name: str) -> str | None:
    if not re.fullmatch(r"[A-Za-z0-9_.+-]+", name):
        return None
    found = shutil.which(name, path=_SAFE_PATH)
    if not found:
        return None
    resolved = Path(found).resolve()
    trusted = (Path("/usr"), Path("/bin"), Path("/opt/homebrew"), Path("/usr/local"))
    return str(resolved) if any(resolved.is_relative_to(root) for root in trusted) else None


def _run(argv: list[str], cwd: str) -> str:
    try:
        return subprocess.run(
            argv, cwd=cwd, capture_output=True, text=True, timeout=0.4,
            env={"PATH": _SAFE_PATH, "HOME": str(Path.home()), "LANG": "C"},
            check=False,
        ).stdout[:64_000]
    except (OSError, subprocess.SubprocessError):
        return ""


def _entry(name: str, prefix: str, description: str | None = None,
           nospace: bool = False) -> TerminalCompletionEntry | None:
    if len(name) > 512 or not _TOKEN.fullmatch(name):
        return None
    at = name.casefold().find(prefix.casefold())
    if prefix and at < 0:
        return None
    return TerminalCompletionEntry(
        name=name, dir=False, at=max(0, at),
        kind="flag" if name.startswith("-") else "sub",
        description=description[:512] if description else None,
        nospace=nospace,
    )


def _cobra(executable: str, argv: list[str], token: str, cwd: str) -> list[TerminalCompletionEntry]:
    lines = _run([executable, "__complete", *argv[1:], token], cwd).splitlines()
    directive = 0
    if lines and lines[-1].startswith(":"):
        try:
            directive = int(lines.pop()[1:])
        except ValueError:
            return []
    if directive & 1:  # ShellCompDirectiveError
        return []
    result: list[TerminalCompletionEntry] = []
    for line in lines:
        name, _, description = line.partition("\t")
        item = _entry(name, token, description or None, bool(directive & 2))
        if item is not None:
            result.append(item)
    return result[:50]


def _git(executable: str, argv: list[str], token: str, cwd: str) -> list[TerminalCompletionEntry]:
    if len(argv) != 1 or token.startswith("-"):
        return []
    output = _run([executable, "--list-cmds=main,others,nohelpers,alias"], cwd)
    return [item for name in output.split() if (item := _entry(name, token)) is not None][:50]


def complete_commands(argv: list[str], token: str, cwd: str) -> TerminalCompletionResult:
    executable = _executable(argv[0]) if argv else None
    if executable is None:
        return TerminalCompletionResult(prefix=token)
    if argv[0] in _COBRA:
        entries = _cobra(executable, argv, token, cwd)
    elif argv[0] == "git":
        entries = _git(executable, argv, token, cwd)
    else:
        entries = []
    entries = sorted(
        entries, key=lambda item: (item.at, item.name.casefold()),
    )[:50]
    return TerminalCompletionResult(prefix=token, entries=entries)


__all__ = ["complete_commands"]
