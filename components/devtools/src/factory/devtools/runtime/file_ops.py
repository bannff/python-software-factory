"""Bounded project text reads and directory listing."""
from __future__ import annotations

import hashlib
import os
import stat
from pathlib import Path

from .models import DirectoryEntry, DirectoryListing, FileRead, ProjectBinding
from .path_resolver import PathRefused, nofollow_flag, resolve_path
from .sensitive_policy import ensure_not_sensitive, excluded_dir

_MAX_FILE_BYTES = 1_048_576


def read_file(
    binding: ProjectBinding, relative: str,
    offset: int = 0, limit: int = 2000,
) -> FileRead:
    path = resolve_path(binding, relative, expect="file")
    fd = os.open(path, os.O_RDONLY | nofollow_flag())
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise PathRefused("file identity is not admissible")
        if info.st_size > _MAX_FILE_BYTES:
            raise PathRefused("file exceeds read limit")
        raw = _read_bounded(fd, _MAX_FILE_BYTES + 1)
    finally:
        os.close(fd)
    if b"\x00" in raw:
        raise PathRefused("binary file is not supported")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise PathRefused("file is not UTF-8 text") from exc
    lines = text.splitlines(keepends=True)
    start, count = max(0, offset), max(1, min(limit, 5000))
    content = "".join(lines[start:start + count])
    return FileRead(
        path=relative, content=content, sha256=hashlib.sha256(raw).hexdigest(),
        total_bytes=len(raw), truncated=start > 0 or start + count < len(lines),
    )


def list_dir(
    binding: ProjectBinding, relative: str = ".", limit: int = 500,
) -> DirectoryListing:
    directory = resolve_path(binding, relative, expect="dir")
    root = Path(binding.root).resolve(strict=True)
    output = []
    with os.scandir(directory) as entries:
        for entry in sorted(entries, key=lambda item: item.name.casefold()):
            if entry.is_symlink() or excluded_dir(entry.name):
                continue
            try:
                path = Path(entry.path).resolve(strict=True)
                path.relative_to(root)
                ensure_not_sensitive(root, path, for_write=False)
                info = entry.stat(follow_symlinks=False)
            except (OSError, ValueError, PermissionError):
                continue
            kind = "dir" if stat.S_ISDIR(info.st_mode) else "file"
            if kind == "file" and (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1):
                continue
            output.append(DirectoryEntry(
                path=str(path.relative_to(root)), kind=kind,
                size=info.st_size if kind == "file" else None,
            ))
            if len(output) >= max(1, min(limit, 1000)):
                return DirectoryListing(path=relative, entries=tuple(output), truncated=True)
    return DirectoryListing(path=relative, entries=tuple(output), truncated=False)


def _read_bounded(fd: int, limit: int) -> bytes:
    chunks, total = [], 0
    while total < limit:
        chunk = os.read(fd, min(65_536, limit - total))
        if not chunk:
            break
        chunks.append(chunk)
        total += len(chunk)
    return b"".join(chunks)


__all__ = ["list_dir", "read_file"]
