"""Pinned descriptor hierarchy and lock files for the local CAN store."""
from __future__ import annotations

import os
from pathlib import Path
import stat

def _required_flag(name: str) -> int:
    value = getattr(os, name, None)
    if not isinstance(value, int) or value == 0:
        raise RuntimeError(f"secure lifecycle storage requires os.{name}")
    return value


_NOFOLLOW = _required_flag("O_NOFOLLOW")
_DIRECTORY = _required_flag("O_DIRECTORY")
_DIR_FLAGS = os.O_RDONLY | _NOFOLLOW | _DIRECTORY
_FILE_FLAGS = os.O_RDONLY | _NOFOLLOW


class PinnedLifecycleDirs:
    """Pin the lifecycle hierarchy and reject later pathname substitution."""

    def __init__(self, root: Path) -> None:
        self.root = root.expanduser().absolute()
        self._root_fd = _open_dir_tree(self.root)
        _trusted_directory(os.fstat(self._root_fd))
        self._base_fd = _open_child_dir(self._root_fd, "can_lifecycle", create=True)
        _trusted_directory(os.fstat(self._base_fd))
        self._fds = {
            name: _open_child_dir(self._base_fd, name, create=True)
            for name in ("attempts", "terminals", "effects", "locks")
        }
        for fd in self._fds.values():
            _trusted_directory(os.fstat(fd))
        self._root_identity = os.fstat(self._root_fd)
        self._base_identity = os.fstat(self._base_fd)
        self._identities = {name: os.fstat(fd) for name, fd in self._fds.items()}

    def fd(self, name: str) -> int:
        self.verify(name)
        return self._fds[name]

    def verify(self, name: str) -> None:
        _same_inode(self._root_identity, self.root.lstat(), "lifecycle root substituted")
        _same_inode(
            self._base_identity,
            os.stat("can_lifecycle", dir_fd=self._root_fd, follow_symlinks=False),
            "lifecycle directory substituted",
        )
        _same_inode(
            self._identities[name],
            os.stat(name, dir_fd=self._base_fd, follow_symlinks=False),
            f"lifecycle {name} directory substituted",
        )

    def uri(self, directory: str, name: str) -> str:
        return (self.root / "can_lifecycle" / directory / name).as_uri()

    def close(self) -> None:
        for fd in getattr(self, "_fds", {}).values():
            _close(fd)
        _close(getattr(self, "_base_fd", -1))
        _close(getattr(self, "_root_fd", -1))
        self._fds = {}
        self._base_fd = self._root_fd = -1

    def __del__(self) -> None:
        self.close()


def open_lock(directory_fd: int, name: str) -> int:
    """Open a stable single-link lock relative to a pinned directory."""
    _basename(name)
    try:
        before = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        _regular(before, False)
    except FileNotFoundError:
        before = None
    try:
        fd = os.open(
            name, os.O_RDWR | os.O_CREAT | os.O_EXCL | _NOFOLLOW, 0o600,
            dir_fd=directory_fd,
        )
    except FileExistsError:
        fd = os.open(name, os.O_RDWR | _NOFOLLOW, dir_fd=directory_fd)
    opened = os.fstat(fd)
    _regular(opened, False)
    if before is not None:
        _same_object(before, opened, "lifecycle lock raced while opening")
    verify_lock(directory_fd, name, fd)
    return fd


def verify_lock(directory_fd: int, name: str, fd: int) -> None:
    current = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
    _same_object(os.fstat(fd), current, "lifecycle lock was substituted")


def _open_dir_tree(path: Path) -> int:
    """Create/open each absolute component without following any symlink."""
    descriptor = os.open(os.sep, _DIR_FLAGS)
    try:
        for name in path.parts[1:]:
            _basename(name)
            try:
                os.mkdir(name, 0o700, dir_fd=descriptor)
                os.fsync(descriptor)
            except FileExistsError:
                pass
            child = _open_child_dir(descriptor, name, create=False)
            os.close(descriptor)
            descriptor = child
        return descriptor
    except Exception:
        _close(descriptor)
        raise


def _open_child_dir(parent_fd: int, name: str, *, create: bool) -> int:
    if create:
        try:
            os.mkdir(name, 0o700, dir_fd=parent_fd)
            os.fsync(parent_fd)
        except FileExistsError:
            pass
    before = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    if not stat.S_ISDIR(before.st_mode):
        raise ValueError("lifecycle directory hierarchy is not real")
    fd = os.open(name, _DIR_FLAGS, dir_fd=parent_fd)
    _same_inode(before, os.fstat(fd), "lifecycle directory raced while opening")
    return fd


def _trusted_directory(value: os.stat_result) -> None:
    if value.st_uid not in {0, os.geteuid()} or value.st_mode & 0o022:
        raise ValueError("lifecycle directory must be trusted and non-writable by peers")


def _regular(value: os.stat_result, immutable: bool) -> None:
    if not stat.S_ISREG(value.st_mode) or value.st_nlink != 1:
        raise ValueError("lifecycle object must be a single-link regular file")
    if immutable and value.st_mode & 0o222:
        raise ValueError("immutable lifecycle object is writable")


def _same_inode(left: os.stat_result, right: os.stat_result, message: str) -> None:
    if stat.S_IFMT(left.st_mode) != stat.S_IFMT(right.st_mode) or (
        left.st_dev, left.st_ino
    ) != (right.st_dev, right.st_ino):
        raise ValueError(message)


def _same_object(left: os.stat_result, right: os.stat_result, message: str) -> None:
    _same_inode(left, right, message)
    if any(getattr(left, field) != getattr(right, field) for field in (
        "st_nlink", "st_size", "st_mtime_ns",
    )):
        raise ValueError(message)


def _basename(name: str) -> None:
    if not name or name in {".", ".."} or "/" in name or "\0" in name:
        raise ValueError("lifecycle object name is invalid")


def _close(fd: int) -> None:
    if fd >= 0:
        try:
            os.close(fd)
        except OSError:
            pass


__all__ = ["PinnedLifecycleDirs", "open_lock", "verify_lock"]
