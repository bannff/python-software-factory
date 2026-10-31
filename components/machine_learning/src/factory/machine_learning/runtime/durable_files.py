"""Symlink-resistant durable local publication primitives."""
from __future__ import annotations

from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import secrets
import stat
from typing import Any, Iterator

_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)
_DIRECTORY = getattr(os, "O_DIRECTORY", 0)


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode() + b"\n"


@contextmanager
def file_lock(path: Path) -> Iterator[None]:
    fd = os.open(path, os.O_RDWR | os.O_CREAT | _NOFOLLOW, 0o600)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise ValueError("durable publication lock is invalid")
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def read_regular(path: Path) -> bytes:
    fd = os.open(path, os.O_RDONLY | _NOFOLLOW)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise ValueError("durable publication file is not regular")
        chunks = []
        while chunk := os.read(fd, 1024 * 1024):
            chunks.append(chunk)
        return b"".join(chunks)
    finally:
        os.close(fd)


def write_exclusive(path: Path, content: bytes) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | _NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(content); stream.flush(); os.fsync(stream.fileno())


def atomic_replace_json(path: Path, value: Any) -> None:
    temp = path.parent / f".{path.name}.{secrets.token_hex(8)}.tmp"
    try:
        write_exclusive(temp, canonical_json(value))
        if path.is_symlink():
            raise ValueError("durable publication path cannot be a symlink")
        os.replace(temp, path)
        fsync_directory(path.parent)
    finally:
        try:
            temp.unlink()
        except FileNotFoundError:
            pass


def fsync_directory(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY | _DIRECTORY | _NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def fsync_tree(root: Path) -> None:
    paths = [root]
    for directory, dirs, files in os.walk(root, followlinks=False):
        paths.extend(Path(directory) / name for name in dirs + files)
    for path in reversed(paths):
        flags = os.O_RDONLY | _NOFOLLOW
        if path.is_dir():
            flags |= _DIRECTORY
        fd = os.open(path, flags)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


__all__ = [
    "atomic_replace_json", "canonical_json", "file_lock", "fsync_directory",
    "fsync_tree", "read_regular", "write_exclusive",
]
