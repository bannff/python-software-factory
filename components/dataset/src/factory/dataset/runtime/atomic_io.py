"""Crash-safe, symlink-resistant local file publication primitives."""
from __future__ import annotations

import os
from pathlib import Path
import stat
import uuid

_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)
_DIRECTORY = getattr(os, "O_DIRECTORY", 0)


def atomic_write(path: Path, content: bytes, *, readonly: bool = False) -> None:
    """Replace one file through a pinned, no-follow parent directory fd."""
    target = _canonical_system_root_alias(path)
    parent_fd = _open_parent(target, create=True)
    temporary = f".{target.name}.{uuid.uuid4().hex}.tmp"
    try:
        descriptor = os.open(
            temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | _NOFOLLOW,
            0o600, dir_fd=parent_fd,
        )
        try:
            _write_all(descriptor, content)
            os.fsync(descriptor)
            if readonly:
                os.fchmod(descriptor, 0o444)
        finally:
            os.close(descriptor)
        os.replace(
            temporary, target.name, src_dir_fd=parent_fd, dst_dir_fd=parent_fd,
        )
        os.fsync(parent_fd)
    finally:
        _unlink(temporary, parent_fd)
        os.close(parent_fd)


def atomic_create_immutable(path: Path, content: bytes) -> bool:
    """Atomically create readonly bytes; return false when the leaf exists."""
    target = _canonical_system_root_alias(path)
    parent_fd = _open_parent(target, create=True)
    temporary = f".{target.name}.{uuid.uuid4().hex}.tmp"
    try:
        descriptor = os.open(
            temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | _NOFOLLOW,
            0o600, dir_fd=parent_fd,
        )
        try:
            _write_all(descriptor, content)
            os.fsync(descriptor)
            os.fchmod(descriptor, 0o444)
        finally:
            os.close(descriptor)
        try:
            os.link(
                temporary, target.name, src_dir_fd=parent_fd,
                dst_dir_fd=parent_fd, follow_symlinks=False,
            )
            os.fsync(parent_fd)
            return True
        except FileExistsError:
            return False
    finally:
        _unlink(temporary, parent_fd)
        os.close(parent_fd)


def atomic_write_immutable(path: Path, content: bytes) -> None:
    """Atomically create immutable bytes or verify the exact prior content."""
    if not atomic_create_immutable(path, content) and read_bytes_no_follow(path) != content:
        raise ValueError(f"Immutable artifact already exists with different content: {path}")


def read_bytes_no_follow(path: Path, *, max_bytes: int | None = None) -> bytes:
    """Read one regular file through a no-follow descriptor chain."""
    target = _canonical_system_root_alias(path)
    parent_fd = _open_parent(target, create=False)
    try:
        return _read_name(parent_fd, target.name, max_bytes=max_bytes)
    finally:
        os.close(parent_fd)


def open_file_no_follow(path: Path, flags: int, mode: int = 0o600) -> int:
    """Open a leaf through a pinned no-follow parent chain."""
    target = _canonical_system_root_alias(path)
    parent_fd = _open_parent(target, create=False)
    try:
        return os.open(target.name, flags | _NOFOLLOW, mode, dir_fd=parent_fd)
    finally:
        os.close(parent_fd)


def _open_parent(path: Path, *, create: bool) -> int:
    absolute = Path(os.path.abspath(path))
    descriptor = os.open(absolute.anchor, os.O_RDONLY | _DIRECTORY)
    try:
        for part in absolute.parts[1:-1]:
            try:
                child = os.open(
                    part, os.O_RDONLY | _DIRECTORY | _NOFOLLOW,
                    dir_fd=descriptor,
                )
            except FileNotFoundError:
                if not create:
                    raise
                os.mkdir(part, 0o755, dir_fd=descriptor)
                child = os.open(
                    part, os.O_RDONLY | _DIRECTORY | _NOFOLLOW,
                    dir_fd=descriptor,
                )
            os.close(descriptor)
            descriptor = child
        return descriptor
    except Exception:
        os.close(descriptor)
        raise


def _read_name(parent_fd: int, name: str, *, max_bytes: int | None = None) -> bytes:
    descriptor = os.open(name, os.O_RDONLY | _NOFOLLOW, dir_fd=parent_fd)
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise ValueError("artifact path is not a regular file")
        if max_bytes is not None:
            if type(max_bytes) is not int or max_bytes <= 0:
                raise ValueError("max_bytes must be a positive integer")
            if metadata.st_size > max_bytes:
                raise ValueError("artifact exceeds configured max size before read")
        chunks = []
        total = 0
        while chunk := os.read(descriptor, 1024 * 1024):
            total += len(chunk)
            if max_bytes is not None and total > max_bytes:
                raise ValueError("artifact exceeds configured max size during read")
            chunks.append(chunk)
        return b"".join(chunks)
    finally:
        os.close(descriptor)


def _write_all(descriptor: int, content: bytes) -> None:
    view = memoryview(content)
    while view:
        view = view[os.write(descriptor, view):]


def _unlink(name: str, parent_fd: int) -> None:
    try:
        os.unlink(name, dir_fd=parent_fd)
    except FileNotFoundError:
        pass


def _canonical_system_root_alias(path: Path) -> Path:
    absolute = Path(os.path.abspath(path.expanduser()))
    if len(absolute.parts) < 2:
        return absolute
    first = Path(absolute.anchor) / absolute.parts[1]
    if first.is_symlink() and first.lstat().st_uid == 0:
        target = Path(os.readlink(first))
        base = target if target.is_absolute() else first.parent / target
        return base.joinpath(*absolute.parts[2:])
    return absolute


__all__ = [
    "atomic_create_immutable", "atomic_write", "atomic_write_immutable",
    "open_file_no_follow", "read_bytes_no_follow",
]
