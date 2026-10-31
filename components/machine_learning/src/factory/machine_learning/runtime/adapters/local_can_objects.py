"""Stable descriptor-relative object I/O for the local CAN lifecycle store."""
from __future__ import annotations

import os
import secrets

from .local_can_files import _NOFOLLOW, _basename, _regular, _same_inode, _same_object

_FILE_FLAGS = os.O_RDONLY | _NOFOLLOW
_MAX_OBJECT = 16 * 1024 * 1024


def read_regular(directory_fd: int, name: str, *, immutable: bool = False) -> bytes:
    """Read one stable, single-link regular file without following links."""
    _basename(name)
    before = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
    _regular(before, immutable)
    fd = os.open(name, _FILE_FLAGS, dir_fd=directory_fd)
    try:
        opened = os.fstat(fd)
        _same_object(before, opened, "lifecycle object raced before read")
        chunks, total = [], 0
        while chunk := os.read(fd, 65_536):
            total += len(chunk)
            if total > _MAX_OBJECT:
                raise ValueError("lifecycle object exceeds size limit")
            chunks.append(chunk)
        after = os.fstat(fd)
    finally:
        os.close(fd)
    current = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
    _same_object(opened, after, "lifecycle object changed during read")
    _same_object(after, current, "lifecycle object substituted after read")
    return b"".join(chunks)


def write_atomic(directory_fd: int, name: str, content: bytes) -> None:
    """Atomically replace one regular file relative to a pinned directory."""
    _basename(name)
    _reject_bad_existing(directory_fd, name)
    temp = f".ml-can-{secrets.token_hex(16)}"
    fd = os.open(
        temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | _NOFOLLOW, 0o600,
        dir_fd=directory_fd,
    )
    try:
        _write_all(fd, content)
        os.fsync(fd)
        before = os.fstat(fd)
        os.replace(temp, name, src_dir_fd=directory_fd, dst_dir_fd=directory_fd)
        current = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        _same_inode(before, current, "lifecycle attempt swapped during publication")
        _same_inode(
            before, os.fstat(fd), "lifecycle attempt fd changed during publication",
        )
        os.fsync(directory_fd)
        current = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        _same_inode(
            os.fstat(fd), current,
            "lifecycle attempt swapped while finalizing publication",
        )
    finally:
        os.close(fd)
        try:
            os.unlink(temp, dir_fd=directory_fd)
        except FileNotFoundError:
            pass
    if read_regular(directory_fd, name) != content:
        raise ValueError("lifecycle attempt changed during publication")


def write_immutable(directory_fd: int, name: str, content: bytes) -> None:
    """Publish one immutable object with no-replace link semantics."""
    _basename(name)
    temp = f".ml-can-{secrets.token_hex(16)}"
    fd = os.open(
        temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | _NOFOLLOW, 0o600,
        dir_fd=directory_fd,
    )
    try:
        _write_all(fd, content)
        os.fsync(fd)
        os.fchmod(fd, 0o400)
        os.fsync(fd)
    finally:
        os.close(fd)
    try:
        try:
            os.link(
                temp, name, src_dir_fd=directory_fd, dst_dir_fd=directory_fd,
                follow_symlinks=False,
            )
        except FileExistsError:
            if read_regular(directory_fd, name, immutable=True) != content:
                raise ValueError("immutable lifecycle object already differs")
        finally:
            os.unlink(temp, dir_fd=directory_fd)
        os.fsync(directory_fd)
    finally:
        try:
            os.unlink(temp, dir_fd=directory_fd)
        except FileNotFoundError:
            pass
    if read_regular(directory_fd, name, immutable=True) != content:
        raise ValueError("immutable lifecycle object changed during publication")


def _write_all(fd: int, content: bytes) -> None:
    view = memoryview(content)
    while view:
        view = view[os.write(fd, view):]


def _reject_bad_existing(directory_fd: int, name: str) -> None:
    try:
        _regular(os.stat(name, dir_fd=directory_fd, follow_symlinks=False), False)
    except FileNotFoundError:
        return


__all__ = ["read_regular", "write_atomic", "write_immutable"]
