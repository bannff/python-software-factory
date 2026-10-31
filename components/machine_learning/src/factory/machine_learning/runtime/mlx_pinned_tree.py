"""Pinned descriptor authority for verified MLX object consumption."""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import stat
from typing import Iterator

from .durable_files import canonical_json
from .passport_paths import reject_symlink_ancestors
from .passport_tree_manifest import MAX_FILE_BYTES, MAX_TREE_BYTES
from .passport_validation import canonical_json as manifest_json

_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)
_DIRECTORY = getattr(os, "O_DIRECTORY", 0)
_FILE_FLAGS = os.O_RDONLY | _NOFOLLOW
_DIR_FLAGS = _FILE_FLAGS | _DIRECTORY
_APPROVED = ("factory_model.json", "model.safetensors")


class PinnedMlxTree:
    """Keep pointer parent and selected object descriptors pinned until close."""

    def __init__(self, reference: str | Path, expected_digest: str | None = None):
        self.reference = Path(reference).expanduser().absolute()
        reject_symlink_ancestors(self.reference.parent)
        self.parent_fd = os.open(self.reference.parent, _DIR_FLAGS)
        try:
            raw, self._ref_stat = _read_regular(self.parent_fd, self.reference.name, 0o400)
            payload = _parse_ref(raw, expected_digest)
            self.digest, self.object_name = payload["digest"], payload["object_path"]
            self.object_fd = os.open(self.object_name, _DIR_FLAGS, dir_fd=self.parent_fd)
            self._object_stat = os.fstat(self.object_fd)
            _require_directory(self._object_stat)
            self.manifest = self._manifest()
            self.manifest_digest = _manifest_digest(self.manifest)
            if self.manifest_digest != self.digest:
                raise ValueError("MLX reference does not match exact object bytes")
        except Exception:
            self.close()
            raise

    @property
    def object_path(self) -> Path:
        """Inspection-only namespace path; consumers must use descriptor methods."""
        return self.reference.parent / self.object_name

    def read_bytes(self, name: str) -> bytes:
        with self.open_file(name) as descriptor:
            chunks = []
            while chunk := os.read(descriptor, 1024 * 1024):
                chunks.append(chunk)
            return b"".join(chunks)

    @contextmanager
    def open_file(self, name: str) -> Iterator[int]:
        if name not in _APPROVED:
            raise ValueError("MLX object file is not approved")
        before = os.stat(name, dir_fd=self.object_fd, follow_symlinks=False)
        descriptor = os.open(name, _FILE_FLAGS, dir_fd=self.object_fd)
        try:
            opened = os.fstat(descriptor)
            _require_file(opened)
            _same(before, opened, "MLX object file raced")
            yield descriptor
            after = os.fstat(descriptor)
        finally:
            os.close(descriptor)
        current = os.stat(name, dir_fd=self.object_fd, follow_symlinks=False)
        _same(opened, after, "MLX object file changed")
        _same(after, current, "MLX object file was substituted")

    def verify(self) -> None:
        raw, current_ref = _read_regular(self.parent_fd, self.reference.name, 0o400)
        payload = _parse_ref(raw, self.digest)
        if payload["object_path"] != self.object_name:
            raise ValueError("MLX reference authority changed while reading")
        _same(self._ref_stat, current_ref, "MLX reference changed while reading")
        current_object = os.stat(
            self.object_name, dir_fd=self.parent_fd, follow_symlinks=False,
        )
        _same(self._object_stat, os.fstat(self.object_fd), "MLX object changed while reading")
        _same(self._object_stat, current_object, "MLX object authority changed while reading")
        if _manifest_digest(self._manifest()) != self.manifest_digest:
            raise ValueError("MLX pinned manifest changed while reading")

    def close(self) -> None:
        object_fd = getattr(self, "object_fd", None)
        if object_fd is not None:
            os.close(object_fd)
            del self.object_fd
        parent_fd = getattr(self, "parent_fd", None)
        if parent_fd is not None:
            os.close(parent_fd)
            del self.parent_fd

    def _manifest(self) -> dict:
        with os.scandir(self.object_fd) as iterator:
            names = sorted(entry.name for entry in iterator)
        if names != list(_APPROVED):
            raise ValueError("MLX native tree must contain exactly two approved files")
        entries, total = [], 0
        for name in names:
            with self.open_file(name) as descriptor:
                digest, size = hashlib.sha256(), 0
                while chunk := os.read(descriptor, 1024 * 1024):
                    size += len(chunk)
                    if size > MAX_FILE_BYTES or total + size > MAX_TREE_BYTES:
                        raise ValueError("MLX tree exceeds byte limit")
                    digest.update(chunk)
            total += size
            entries.append({
                "path": name, "type": "file", "size_bytes": size,
                "sha256": digest.hexdigest(),
            })
        return {"schema_version": "1.0", "entries": entries, "total_size_bytes": total}


def open_pinned_mlx_tree(
    reference: str | Path, expected_digest: str | None = None,
) -> PinnedMlxTree:
    return PinnedMlxTree(reference, expected_digest)


def _read_regular(parent_fd: int, name: str, mode: int) -> tuple[bytes, os.stat_result]:
    descriptor = os.open(name, _FILE_FLAGS, dir_fd=parent_fd)
    try:
        info = os.fstat(descriptor)
        if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
                or stat.S_IMODE(info.st_mode) != mode or info.st_uid != os.geteuid()):
            raise ValueError("MLX reference is not a sealed regular file")
        chunks = []
        while chunk := os.read(descriptor, 4096):
            chunks.append(chunk)
        return b"".join(chunks), info
    finally:
        os.close(descriptor)


def _parse_ref(raw: bytes, expected: str | None) -> dict[str, str]:
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("MLX reference is unreadable") from exc
    valid_digest = isinstance(value, dict) and isinstance(value.get("digest"), str)
    valid_name = isinstance(value, dict) and isinstance(value.get("object_path"), str)
    if (not isinstance(value, dict) or set(value) != {"digest", "object_path", "schema_version"}
            or value.get("schema_version") != "1.0" or raw != canonical_json(value)
            or not valid_digest or len(value["digest"]) != 64
            or any(ch not in "0123456789abcdef" for ch in value["digest"])
            or expected is not None and value["digest"] != expected
            or not valid_name or not value["object_path"].startswith(".")
            or Path(value["object_path"]).name != value["object_path"]):
        raise ValueError("MLX reference does not match canonical authority")
    return value


def _require_directory(info: os.stat_result) -> None:
    if (not stat.S_ISDIR(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o500
            or info.st_uid != os.geteuid()):
        raise ValueError("MLX reference object is not a sealed directory")


def _require_file(info: os.stat_result) -> None:
    if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
            or stat.S_IMODE(info.st_mode) != 0o400 or info.st_uid != os.geteuid()):
        raise ValueError("MLX object file is not sealed read-only")


def _same(left: os.stat_result, right: os.stat_result, message: str) -> None:
    fields = ("st_dev", "st_ino", "st_mode", "st_nlink", "st_size", "st_mtime_ns", "st_ctime_ns")
    if any(getattr(left, field) != getattr(right, field) for field in fields):
        raise ValueError(message)


def _manifest_digest(manifest: dict) -> str:
    return hashlib.sha256(manifest_json(manifest)).hexdigest()


__all__ = ["PinnedMlxTree", "open_pinned_mlx_tree"]
