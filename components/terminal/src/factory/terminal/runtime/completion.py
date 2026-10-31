"""Bounded filesystem completion for an authenticated Terminal session."""
from __future__ import annotations

import heapq
import os
from pathlib import Path

from .models import TerminalCompletionEntry, TerminalCompletionResult

MAX_ENTRIES = 50
MAX_SCAN = 2_000
_SENSITIVE = (".ssh", ".aws", ".gnupg")
_SENSITIVE_ROOTS = tuple(
    str((Path.home() / name).resolve(strict=False)) for name in _SENSITIVE
)


def _unsafe(name: str) -> bool:
    return any(ord(char) < 32 or ord(char) == 127 or 0xD800 <= ord(char) <= 0xDFFF
               for char in name)


def _split(token: str) -> tuple[str, str]:
    index = token.rfind("/")
    return (token[:index + 1], token[index + 1:]) if index >= 0 else ("", token)


def _directory(cwd: str, part: str) -> str:
    expanded = os.path.expanduser(part)
    if os.path.isabs(expanded):
        return os.path.abspath(expanded)
    return os.path.abspath(os.path.join(cwd, expanded))


def _within(path: str, root: str) -> bool:
    try:
        return os.path.commonpath((path, root)) == root
    except ValueError:
        return False


def _sensitive(path: str) -> bool:
    canonical = os.path.realpath(path)
    return any(_within(canonical, root) for root in _SENSITIVE_ROOTS)


def _open_directory(path: str) -> int | None:
    try:
        canonical = os.path.realpath(path)
        if _sensitive(canonical):
            return None
        flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(canonical, flags)
        opened, named = os.fstat(descriptor), os.stat(canonical)
        if (opened.st_dev, opened.st_ino) != (named.st_dev, named.st_ino):
            os.close(descriptor)
            return None
        return descriptor
    except OSError:
        return None


def complete_paths(
    cwd: str, token: str, folders_only: bool,
) -> TerminalCompletionResult:
    """List ranked path candidates without materializing an unbounded directory."""
    part, prefix = _split(token)
    lexical = _directory(cwd, part)
    descriptor = _open_directory(lexical)
    if descriptor is None:
        return TerminalCompletionResult(prefix=prefix)
    hidden = prefix.startswith(".")
    lowered = prefix.casefold()
    scanned = matched = 0
    capped = False

    def candidates():
        nonlocal scanned, matched, capped
        with os.scandir(descriptor) as entries:
            for entry in entries:
                if scanned >= MAX_SCAN:
                    capped = True
                    break
                scanned += 1
                name = entry.name
                if _unsafe(name) or (name.startswith(".") and not hidden):
                    continue
                folded = name.casefold()
                at = (0 if folded.startswith(lowered) else -1) if hidden else folded.find(lowered)
                if at < 0 or _sensitive(os.path.join(lexical, name)):
                    continue
                try:
                    is_dir = entry.is_dir(follow_symlinks=True)
                except OSError:
                    is_dir = False
                if folders_only and not is_dir:
                    continue
                matched += 1
                yield TerminalCompletionEntry(name=name, dir=is_dir, at=at)

    try:
        selected = heapq.nsmallest(
            MAX_ENTRIES, candidates(),
            key=lambda item: (item.at, not item.dir, item.name.casefold()),
        )
    except OSError:
        selected = []
    finally:
        os.close(descriptor)
    return TerminalCompletionResult(
        directory=lexical, prefix=prefix, entries=selected,
        truncated=capped or matched > MAX_ENTRIES,
    )


__all__ = ["MAX_ENTRIES", "MAX_SCAN", "complete_paths"]
