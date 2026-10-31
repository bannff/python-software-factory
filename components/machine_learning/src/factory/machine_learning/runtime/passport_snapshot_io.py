"""Descriptor-safe bounded copy and re-verification for passport artifacts."""
from __future__ import annotations

import os
import stat
from pathlib import Path
from urllib.parse import unquote, urlparse

from .durable_files import fsync_directory, fsync_tree
from .mlx_publication import (
    publication_lock, publish_mlx_reference, verified_mlx_tree,
)
from .passport_artifacts import verify_artifact_ref
from .passport_paths import require_contained_directory, require_contained_file
from .passport_refs import PassportArtifactRef
from .passport_tree_manifest import (
    MAX_FILE_BYTES, MAX_NAME_BYTES, MAX_TREE_BYTES, MAX_TREE_DEPTH, MAX_TREE_ENTRIES,
)
from .passport_tree_seal import seal_read_only_tree

_TREE_FORMATS = frozenset({
    "mlflow-lightgbm", "transformers-patchtst", "mlx-safetensors",
    "chronos2-native-probe", "chronos2-backbone",
})
_SEALED_FORMATS = frozenset({
    "mlx-safetensors", "chronos2-native-probe", "chronos2-backbone",
})
_CHUNK = 1024 * 1024
_FILE_FLAGS = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
_DIR_FLAGS = _FILE_FLAGS | getattr(os, "O_DIRECTORY", 0)


def copy_verified_artifact(
    ref: PassportArtifactRef, storage_root: str | Path, destination: Path,
) -> None:
    """Verify, fd-copy with bounds, then reverify both source and copied bytes."""
    root = Path(storage_root).expanduser().absolute()
    verify_artifact_ref(ref, root)
    source = _file_path(ref.uri)
    if ref.format == "mlx-safetensors":
        object_copy = destination.parent / f".{destination.name}.mlx-object"
        with verified_mlx_tree(source, ref.digest) as source_tree:
            _copy_tree_fd(source_tree.object_fd, object_copy)
        seal_read_only_tree(object_copy)
        fsync_tree(object_copy)
        fsync_directory(destination.parent)
        with publication_lock(destination):
            publish_mlx_reference(destination, object_copy, ref.digest)
    elif ref.format in _TREE_FORMATS:
        _copy_tree(require_contained_directory(source, root), destination)
        if ref.format in _SEALED_FORMATS:
            seal_read_only_tree(destination)
    else:
        _copy_path(require_contained_file(source, root), destination)
    copied = ref.model_copy(update={"uri": destination.resolve().as_uri()})
    verify_artifact_ref(copied, destination.parent)
    verify_artifact_ref(ref, root)


def _copy_tree_fd(source_fd: int, destination: Path) -> None:
    destination.mkdir(mode=0o700)
    _copy_directory_fd(source_fd, destination, 0, {"entries": 0, "total": 0})


def _copy_tree(source: Path, destination: Path) -> None:
    before = source.lstat()
    source_fd = os.open(source, _DIR_FLAGS)
    budget = {"entries": 0, "total": 0}
    try:
        opened = os.fstat(source_fd)
        _stable_or_raise(before, opened, "source directory raced")
        destination.mkdir(mode=0o700)
        _copy_directory_fd(source_fd, destination, 0, budget)
        after = os.fstat(source_fd)
    finally:
        os.close(source_fd)
    _stable_or_raise(before, after, "source directory changed")
    _stable_or_raise(after, source.lstat(), "source directory was substituted")


def _copy_directory_fd(
    source_fd: int, destination: Path, depth: int, budget: dict[str, int],
) -> None:
    if depth > MAX_TREE_DEPTH:
        raise ValueError("ModelPassport snapshot exceeds maximum depth")
    with os.scandir(source_fd) as iterator:
        entries = sorted(iterator, key=lambda item: item.name)
    for entry in entries:
        _validate_name(entry.name)
        budget["entries"] += 1
        if budget["entries"] > MAX_TREE_ENTRIES:
            raise ValueError("ModelPassport snapshot exceeds entry limit")
        before = entry.stat(follow_symlinks=False)
        target = destination / entry.name
        if stat.S_ISDIR(before.st_mode):
            child_fd = os.open(entry.name, _DIR_FLAGS, dir_fd=source_fd)
            try:
                opened = os.fstat(child_fd)
                _stable_or_raise(before, opened, "directory raced during snapshot")
                target.mkdir(mode=0o700)
                _copy_directory_fd(child_fd, target, depth + 1, budget)
                after = os.fstat(child_fd)
            finally:
                os.close(child_fd)
        elif stat.S_ISREG(before.st_mode):
            if before.st_nlink != 1:
                raise ValueError("ModelPassport snapshot rejects hard-linked files")
            child_fd = os.open(entry.name, _FILE_FLAGS, dir_fd=source_fd)
            try:
                opened = os.fstat(child_fd)
                _stable_or_raise(before, opened, "file raced during snapshot")
                _copy_file_fd(child_fd, target, budget)
                after = os.fstat(child_fd)
            finally:
                os.close(child_fd)
        else:
            raise ValueError("ModelPassport snapshot rejects non-regular entries")
        current = os.stat(entry.name, dir_fd=source_fd, follow_symlinks=False)
        _stable_or_raise(before, after, "snapshot source changed")
        _stable_or_raise(after, current, "snapshot source was substituted")


def _copy_path(source: Path, destination: Path) -> None:
    before = source.lstat()
    descriptor = os.open(source, _FILE_FLAGS)
    try:
        opened = os.fstat(descriptor)
        _require_regular(opened)
        _stable_or_raise(before, opened, "file raced during snapshot")
        _copy_file_fd(descriptor, destination, {"entries": 0, "total": 0})
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    _stable_or_raise(before, after, "snapshot source changed")
    _stable_or_raise(after, source.lstat(), "snapshot source was substituted")


def _copy_file_fd(
    source_fd: int, destination: Path, budget: dict[str, int],
) -> None:
    output_fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o400)
    size = 0
    try:
        while chunk := os.read(source_fd, _CHUNK):
            size += len(chunk)
            if size > MAX_FILE_BYTES or budget["total"] + size > MAX_TREE_BYTES:
                raise ValueError("ModelPassport snapshot exceeds byte limits")
            view = memoryview(chunk)
            while view:
                view = view[os.write(output_fd, view):]
        os.fsync(output_fd)
    finally:
        os.close(output_fd)
    budget["total"] += size


def _require_regular(value: os.stat_result) -> None:
    if not stat.S_ISREG(value.st_mode) or value.st_nlink != 1:
        raise ValueError("ModelPassport snapshot requires unlinked regular files")


def _stable_or_raise(
    left: os.stat_result, right: os.stat_result, message: str,
) -> None:
    fields = (
        "st_dev", "st_ino", "st_mode", "st_nlink", "st_size",
        "st_mtime_ns", "st_ctime_ns",
    )
    if any(getattr(left, field) != getattr(right, field) for field in fields):
        raise ValueError(f"ModelPassport {message}")


def _validate_name(name: str) -> None:
    if not name or name in {".", ".."} or len(os.fsencode(name)) > MAX_NAME_BYTES:
        raise ValueError("ModelPassport snapshot contains an invalid name")


def _file_path(uri: str) -> Path:
    parsed = urlparse(uri)
    if parsed.scheme != "file":
        raise ValueError("ModelPassport snapshots require file URIs")
    return Path(unquote(parsed.path))


__all__ = ["copy_verified_artifact"]
