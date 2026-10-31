"""Descriptor-safe read-only sealing for immutable native model trees."""
from __future__ import annotations

import os
import shutil
import stat
from pathlib import Path

_FILE_FLAGS = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
_DIR_FLAGS = _FILE_FLAGS | getattr(os, "O_DIRECTORY", 0)


def seal_read_only_tree(path: str | Path) -> None:
    """Seal one already-verified tree without following links."""
    root = Path(path)
    before = root.lstat()
    descriptor = os.open(root, _DIR_FLAGS)
    try:
        _same_object(before, os.fstat(descriptor), "tree root raced before sealing")
        _seal_directory(descriptor)
        os.fchmod(descriptor, 0o500)
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    _same_object(before, after, "tree root changed while sealing")
    _same_object(after, root.lstat(), "sealed tree root was substituted")


def require_read_only_tree(path: str | Path) -> None:
    """Require a sealed regular tree while rejecting links and substitutions."""
    root = Path(path)
    before = root.lstat()
    descriptor = os.open(root, _DIR_FLAGS)
    try:
        opened = os.fstat(descriptor)
        _same_object(before, opened, "tree root raced during seal verification")
        _require_not_writable(opened)
        _check_directory(descriptor)
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    _same_object(opened, after, "tree root changed during seal verification")
    _same_object(after, root.lstat(), "verified tree root was substituted")


def remove_staging_tree(path: str | Path) -> None:
    """Remove a private staging tree, including one partially or fully sealed."""
    root = Path(path)
    try:
        root.lstat()
    except FileNotFoundError:
        return
    if root.is_symlink() or not root.is_dir():
        root.unlink()
        return
    for directory, child_directories, files in os.walk(
        root, topdown=True, followlinks=False,
    ):
        os.chmod(directory, 0o700)
        for name in child_directories:
            child = Path(directory) / name
            if not child.is_symlink():
                os.chmod(child, 0o700)
        for name in files:
            child = Path(directory) / name
            if not child.is_symlink():
                os.chmod(child, 0o600)
    shutil.rmtree(root)


def _seal_directory(directory_fd: int) -> None:
    with os.scandir(directory_fd) as iterator:
        entries = sorted(iterator, key=lambda item: item.name)
    for entry in entries:
        before = entry.stat(follow_symlinks=False)
        if stat.S_ISDIR(before.st_mode):
            child_fd = os.open(entry.name, _DIR_FLAGS, dir_fd=directory_fd)
            try:
                _same_object(before, os.fstat(child_fd), "directory raced while sealing")
                _seal_directory(child_fd)
                os.fchmod(child_fd, 0o500)
                after = os.fstat(child_fd)
            finally:
                os.close(child_fd)
        elif stat.S_ISREG(before.st_mode):
            if before.st_nlink != 1:
                raise ValueError("immutable model tree rejects hard-linked files")
            child_fd = os.open(entry.name, _FILE_FLAGS, dir_fd=directory_fd)
            try:
                _same_object(before, os.fstat(child_fd), "file raced while sealing")
                os.fchmod(child_fd, 0o400)
                after = os.fstat(child_fd)
            finally:
                os.close(child_fd)
        else:
            raise ValueError("immutable model tree rejects non-regular entries")
        current = os.stat(entry.name, dir_fd=directory_fd, follow_symlinks=False)
        _same_object(before, after, "model tree entry changed while sealing")
        _same_object(after, current, "sealed model tree entry was substituted")


def _check_directory(directory_fd: int) -> None:
    with os.scandir(directory_fd) as iterator:
        entries = sorted(iterator, key=lambda item: item.name)
    for entry in entries:
        before = entry.stat(follow_symlinks=False)
        flags = _DIR_FLAGS if stat.S_ISDIR(before.st_mode) else _FILE_FLAGS
        if not (stat.S_ISDIR(before.st_mode) or stat.S_ISREG(before.st_mode)):
            raise ValueError("immutable model tree rejects non-regular entries")
        if stat.S_ISREG(before.st_mode) and before.st_nlink != 1:
            raise ValueError("immutable model tree rejects hard-linked files")
        child_fd = os.open(entry.name, flags, dir_fd=directory_fd)
        try:
            opened = os.fstat(child_fd)
            _same_object(before, opened, "sealed model tree entry raced")
            _require_not_writable(opened)
            if stat.S_ISDIR(opened.st_mode):
                _check_directory(child_fd)
            after = os.fstat(child_fd)
        finally:
            os.close(child_fd)
        current = os.stat(entry.name, dir_fd=directory_fd, follow_symlinks=False)
        _same_object(opened, after, "sealed model tree entry changed")
        _same_object(after, current, "sealed model tree entry was substituted")


def _require_not_writable(value: os.stat_result) -> None:
    if value.st_mode & 0o222:
        raise ValueError("immutable model tree is not sealed read-only")


def _same_object(left: os.stat_result, right: os.stat_result, message: str) -> None:
    fields = ("st_dev", "st_ino", "st_nlink", "st_size", "st_mtime_ns")
    if stat.S_IFMT(left.st_mode) != stat.S_IFMT(right.st_mode) or any(
        getattr(left, field) != getattr(right, field) for field in fields
    ):
        raise ValueError(message)


__all__ = ["remove_staging_tree", "require_read_only_tree", "seal_read_only_tree"]
