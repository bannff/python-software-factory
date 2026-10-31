"""Bounded project content and filename discovery."""
from __future__ import annotations

import fnmatch
import os
import time
from pathlib import Path

from .file_ops import read_file
from .models import ProjectBinding, SearchMatch, SearchResult
from .path_resolver import resolve_path
from .sensitive_policy import ensure_not_sensitive, excluded_dir

_MAX_FILES = 2000
_MAX_SECONDS = 2.0


def search(
    binding: ProjectBinding, query: str, relative: str = ".",
    glob: str | None = None, limit: int = 100,
) -> SearchResult:
    root = Path(binding.root).resolve(strict=True)
    start_dir = resolve_path(binding, relative, expect="dir")
    deadline = time.monotonic() + _MAX_SECONDS
    matches, scanned, truncated = [], 0, False
    maximum = max(1, min(limit, 500))
    for current, dirs, files in os.walk(start_dir, followlinks=False):
        dirs[:] = sorted(name for name in dirs if not excluded_dir(name))
        for name in sorted(files):
            if scanned >= _MAX_FILES or time.monotonic() >= deadline:
                truncated = True
                break
            path = Path(current) / name
            try:
                canonical = path.resolve(strict=True)
                canonical.relative_to(root)
                ensure_not_sensitive(root, canonical, for_write=False)
            except (OSError, ValueError, PermissionError):
                continue
            rel = canonical.relative_to(root).as_posix()
            if glob and not (fnmatch.fnmatch(rel, glob) or fnmatch.fnmatch(name, glob)):
                continue
            scanned += 1
            if not query:
                matches.append(SearchMatch(path=rel, text=name))
            else:
                try:
                    content = read_file(binding, rel, 0, 5000).content
                except (OSError, ValueError, PermissionError):
                    continue
                for number, line in enumerate(content.splitlines(), 1):
                    if query.casefold() in line.casefold():
                        matches.append(SearchMatch(
                            path=rel, line=number, text=line[:4096],
                        ))
                        if len(matches) >= maximum:
                            break
            if len(matches) >= maximum:
                truncated = True
                break
        if truncated:
            break
    return SearchResult(
        matches=tuple(matches), truncated=truncated, files_scanned=scanned,
    )


__all__ = ["search"]
