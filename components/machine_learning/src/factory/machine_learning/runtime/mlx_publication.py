"""Exclusive pointer publication and verified MLX handle construction."""
from __future__ import annotations

from contextlib import contextmanager
import os
from pathlib import Path
from typing import Iterator

from .durable_files import canonical_json, file_lock, fsync_directory
from .mlx_darwin_rename import rename_exclusive
from .mlx_local_digest import is_mlx_reference_path, sealed_local_model_artifact_digest
from .mlx_pinned_tree import PinnedMlxTree, open_pinned_mlx_tree
from .passport_tree_seal import require_read_only_tree

_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)


def publication_lock(reference: Path):
    """Serialize cooperating publishers for one digest reference."""
    return file_lock(reference.parent / f".{reference.name}.lock")


def publish_mlx_reference(reference: Path, object_path: Path, digest: str) -> None:
    """Publish one sealed sibling object through a no-replace canonical ref."""
    _remove_stale_temps(reference, digest)
    relative = _relative_object(reference, object_path)
    payload = canonical_json({
        "digest": digest, "object_path": relative, "schema_version": "1.0",
    })
    temporary = reference.parent / f".{reference.name}.{os.urandom(8).hex()}.tmp"
    descriptor = os.open(
        temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | _NOFOLLOW, 0o600,
    )
    try:
        _write_all(descriptor, payload)
        os.fsync(descriptor)
        os.fchmod(descriptor, 0o400)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    try:
        try:
            rename_exclusive(temporary, reference)
            fsync_directory(reference.parent)
        except FileExistsError:
            require_mlx_reference(reference, digest)
        require_mlx_reference(reference, digest)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def require_mlx_reference(
    reference: str | Path, expected_digest: str | None = None,
) -> tuple[Path, str]:
    """Inspect a reference; runtime consumers must use ``verified_mlx_tree``."""
    handle = open_pinned_mlx_tree(reference, expected_digest)
    try:
        handle.verify()
        return handle.object_path, handle.digest
    finally:
        handle.close()


@contextmanager
def verified_mlx_tree(
    reference: str | Path, expected_digest: str | None = None,
) -> Iterator[PinnedMlxTree]:
    """Yield only a descriptor-pinned verified handle, never a reopenable path."""
    handle = open_pinned_mlx_tree(reference, expected_digest)
    try:
        yield handle
    finally:
        try:
            handle.verify()
        finally:
            handle.close()


def _remove_stale_temps(reference: Path, digest: str) -> None:
    """Remove only fully verified same-digest pointer temporaries under the lock."""
    removed = False
    for candidate in reference.parent.glob(f".{reference.name}.*.tmp"):
        handle = None
        try:
            handle = open_pinned_mlx_tree(candidate, digest)
            handle.verify()
            candidate.unlink()
            removed = True
        except (OSError, ValueError):
            continue
        finally:
            if handle is not None:
                handle.close()
    if removed:
        fsync_directory(reference.parent)


def _relative_object(reference: Path, object_path: Path) -> str:
    if object_path.parent.absolute() != reference.parent.absolute():
        raise ValueError("MLX object must be a sibling of its canonical reference")
    name = object_path.name
    if not name.startswith(".") or Path(name).name != name:
        raise ValueError("MLX object path must be a hidden relative name")
    require_read_only_tree(object_path)
    return name


def _write_all(descriptor: int, content: bytes) -> None:
    view = memoryview(content)
    while view:
        view = view[os.write(descriptor, view):]


__all__ = [
    "PinnedMlxTree", "is_mlx_reference_path", "publication_lock",
    "publish_mlx_reference", "require_mlx_reference",
    "sealed_local_model_artifact_digest", "verified_mlx_tree",
]
