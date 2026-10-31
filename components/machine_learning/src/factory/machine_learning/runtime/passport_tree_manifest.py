"""Bounded descriptor-based manifests for immutable model artifact trees."""
from __future__ import annotations

import hashlib
import os
import stat
from pathlib import Path
from typing import Any

from .passport_paths import require_contained_directory

MAX_TREE_ENTRIES = 10_000
MAX_TREE_BYTES = 8 * 1024 * 1024 * 1024
MAX_FILE_BYTES = 2 * 1024 * 1024 * 1024
MAX_TREE_DEPTH = 32
MAX_NAME_BYTES = 255
_CHUNK = 1024 * 1024
_FILE_FLAGS = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
_DIR_FLAGS = _FILE_FLAGS | getattr(os, "O_DIRECTORY", 0)


def bounded_tree_manifest(
    path: str | Path, storage_root: str | Path, identity: str,
    required_files: frozenset[str] = frozenset(),
) -> dict[str, Any]:
    """Hash one complete tree incrementally with hard size and shape limits."""
    root = require_contained_directory(Path(path), Path(storage_root))
    before = root.lstat()
    descriptor = os.open(root, _DIR_FLAGS)
    state: dict[str, Any] = {"entries": [], "count": 0, "total": 0}
    try:
        opened = os.fstat(descriptor)
        _require_stable(before, opened, f"{identity} root raced")
        _walk(descriptor, "", 0, state, identity)
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    _require_stable(before, after, f"{identity} root changed")
    _require_stable(after, root.lstat(), f"{identity} root was substituted")
    files = {item["path"] for item in state["entries"] if item["type"] == "file"}
    if not required_files.issubset(files):
        missing = sorted(required_files - files)
        raise ValueError(f"{identity} tree is incomplete: {missing}")
    return {
        "schema_version": "1.0", "entries": state["entries"],
        "total_size_bytes": state["total"],
    }


def _walk(
    directory_fd: int, prefix: str, depth: int,
    state: dict[str, Any], identity: str,
) -> None:
    if depth > MAX_TREE_DEPTH:
        raise ValueError(f"{identity} tree exceeds maximum depth")
    with os.scandir(directory_fd) as iterator:
        entries = sorted(iterator, key=lambda item: item.name)
    for entry in entries:
        _validate_name(entry.name, identity)
        relative = f"{prefix}/{entry.name}" if prefix else entry.name
        before = entry.stat(follow_symlinks=False)
        _reserve_entry(state, identity)
        if stat.S_ISLNK(before.st_mode):
            raise ValueError(f"{identity} tree rejects symlinks")
        if stat.S_ISDIR(before.st_mode):
            child_fd = os.open(entry.name, _DIR_FLAGS, dir_fd=directory_fd)
            try:
                opened = os.fstat(child_fd)
                _require_stable(before, opened, f"{identity} directory raced")
                state["entries"].append({"path": relative, "type": "directory"})
                _walk(child_fd, relative, depth + 1, state, identity)
                after = os.fstat(child_fd)
            finally:
                os.close(child_fd)
        elif stat.S_ISREG(before.st_mode):
            if before.st_nlink != 1:
                raise ValueError(f"{identity} tree rejects hard-linked files")
            child_fd = os.open(entry.name, _FILE_FLAGS, dir_fd=directory_fd)
            try:
                opened = os.fstat(child_fd)
                _require_stable(before, opened, f"{identity} file raced")
                size, digest = _hash_file(child_fd, state, identity)
                after = os.fstat(child_fd)
            finally:
                os.close(child_fd)
            state["entries"].append({
                "path": relative, "type": "file", "size_bytes": size,
                "sha256": digest,
            })
        else:
            raise ValueError(f"{identity} tree contains a non-regular entry")
        current = os.stat(entry.name, dir_fd=directory_fd, follow_symlinks=False)
        _require_stable(before, after, f"{identity} entry changed")
        _require_stable(after, current, f"{identity} entry was substituted")


def _hash_file(
    descriptor: int, state: dict[str, Any], identity: str,
) -> tuple[int, str]:
    digest = hashlib.sha256()
    size = 0
    while chunk := os.read(descriptor, _CHUNK):
        size += len(chunk)
        if size > MAX_FILE_BYTES:
            raise ValueError(f"{identity} tree file exceeds byte limit")
        if state["total"] + size > MAX_TREE_BYTES:
            raise ValueError(f"{identity} tree exceeds total byte limit")
        digest.update(chunk)
    state["total"] += size
    return size, digest.hexdigest()


def _reserve_entry(state: dict[str, Any], identity: str) -> None:
    state["count"] += 1
    if state["count"] > MAX_TREE_ENTRIES:
        raise ValueError(f"{identity} tree exceeds entry limit")


def _validate_name(name: str, identity: str) -> None:
    if not name or name in {".", ".."} or len(os.fsencode(name)) > MAX_NAME_BYTES:
        raise ValueError(f"{identity} tree contains an invalid name")


def _require_stable(left: os.stat_result, right: os.stat_result, message: str) -> None:
    fields = (
        "st_dev", "st_ino", "st_mode", "st_nlink", "st_size",
        "st_mtime_ns", "st_ctime_ns",
    )
    if any(getattr(left, field) != getattr(right, field) for field in fields):
        raise ValueError(message)


__all__ = [
    "MAX_FILE_BYTES", "MAX_NAME_BYTES", "MAX_TREE_BYTES", "MAX_TREE_DEPTH",
    "MAX_TREE_ENTRIES", "bounded_tree_manifest",
]
