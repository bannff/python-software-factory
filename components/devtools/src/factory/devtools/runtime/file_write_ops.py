"""Atomic project file creation and compare-and-swap editing."""
from __future__ import annotations

import hashlib
import os
import stat
from uuid import uuid4

from .models import FileWrite, ProjectBinding, RelativePath
from .path_resolver import PathRefused, nofollow_flag, resolve_path

_MAX_WRITE_BYTES = 1_048_576


class EditConflict(RuntimeError):
    pass


def create_file(binding: ProjectBinding, relative: str, content: str) -> FileWrite:
    raw = _content(content)
    path = resolve_path(binding, relative, for_write=True)
    parent_fd = os.open(path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        fd = os.open(
            path.name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | nofollow_flag(),
            0o644, dir_fd=parent_fd,
        )
        try:
            _write_all(fd, raw)
            os.fsync(fd)
        finally:
            os.close(fd)
    finally:
        os.close(parent_fd)
    return _result(relative, raw, True)


def edit_file(
    binding: ProjectBinding, relative: str, content: str, base_sha256: str,
) -> FileWrite:
    if len(base_sha256) != 64 or any(char not in "0123456789abcdef" for char in base_sha256):
        raise ValueError("base_sha256 must be lowercase SHA-256")
    raw = _content(content)
    path = resolve_path(binding, relative, expect="file", for_write=True)
    parent_fd = os.open(path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    temp_name = f".devtools-{uuid4().hex}.tmp"
    try:
        source_fd = os.open(path.name, os.O_RDONLY | nofollow_flag(), dir_fd=parent_fd)
        try:
            before = os.fstat(source_fd)
            if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
                raise PathRefused("file identity is not admissible")
            current = _read_all(source_fd, _MAX_WRITE_BYTES + 1)
            if hashlib.sha256(current).hexdigest() != base_sha256:
                raise EditConflict("file changed since read")
        finally:
            os.close(source_fd)
        target_fd = os.open(
            temp_name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | nofollow_flag(),
            stat.S_IMODE(before.st_mode), dir_fd=parent_fd,
        )
        try:
            _write_all(target_fd, raw)
            os.fsync(target_fd)
        finally:
            os.close(target_fd)
        latest = os.stat(path.name, dir_fd=parent_fd, follow_symlinks=False)
        identity = ("st_dev", "st_ino", "st_size", "st_mtime_ns")
        if any(getattr(latest, key) != getattr(before, key) for key in identity):
            raise EditConflict("file changed during edit")
        os.replace(
            temp_name, path.name, src_dir_fd=parent_fd, dst_dir_fd=parent_fd,
        )
    finally:
        try:
            os.unlink(temp_name, dir_fd=parent_fd)
        except FileNotFoundError:
            pass
        os.close(parent_fd)
    return _result(relative, raw, False)


def _content(content: str) -> bytes:
    raw = content.encode("utf-8")
    if len(raw) > _MAX_WRITE_BYTES or b"\x00" in raw:
        raise ValueError("file content is not admissible")
    return raw


def _write_all(fd: int, value: bytes) -> None:
    view = memoryview(value)
    while view:
        written = os.write(fd, view)
        if written <= 0:
            raise OSError("file write made no progress")
        view = view[written:]


def _read_all(fd: int, limit: int) -> bytes:
    chunks, total = [], 0
    while total < limit:
        chunk = os.read(fd, min(65_536, limit - total))
        if not chunk:
            break
        chunks.append(chunk)
        total += len(chunk)
    if total > _MAX_WRITE_BYTES:
        raise PathRefused("file exceeds edit limit")
    return b"".join(chunks)


def _result(relative: str, raw: bytes, created: bool) -> FileWrite:
    RelativePath(path=relative)
    return FileWrite(
        path=relative, sha256=hashlib.sha256(raw).hexdigest(),
        total_bytes=len(raw), created=created,
    )


__all__ = ["EditConflict", "create_file", "edit_file"]
