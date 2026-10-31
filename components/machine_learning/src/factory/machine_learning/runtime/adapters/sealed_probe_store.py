"""Descriptor-confined content-addressed storage for conformance probes."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path

from ..passport_probe_contracts import PassportProbeResult
from ..passport_refs import PassportArtifactRef
from ..passport_validation import canonical_json
from .local_can_files import _open_child_dir, _open_dir_tree, _same_inode
from .local_can_objects import read_regular, write_immutable


class SealedProbeStore:
    """Pin the ML evidence hierarchy and publish immutable canonical probes."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).expanduser().absolute()
        self._root_fd = _open_dir_tree(self.root)
        self._base_fd = _open_child_dir(
            self._root_fd, "conformance_evidence", create=True,
        )
        self._objects_fd = _open_child_dir(self._base_fd, "objects", create=True)
        self._root_stat = os.fstat(self._root_fd)
        self._base_stat = os.fstat(self._base_fd)
        self._objects_stat = os.fstat(self._objects_fd)

    def publish(self, result: PassportProbeResult) -> PassportArtifactRef:
        raw = canonical_json(result.model_dump(mode="json"))
        digest = hashlib.sha256(raw).hexdigest()
        name = f"{digest}.json"
        self._verify()
        write_immutable(self._objects_fd, name, raw)
        self._verify()
        return PassportArtifactRef(
            role="conformance_evidence", uri=self._path(name).as_uri(),
            digest=digest, media_type="application/json", format="json",
            size_bytes=len(raw),
        )

    def read(self, ref: PassportArtifactRef) -> PassportProbeResult:
        self._verify()
        name = f"{ref.digest}.json"
        if (
            ref.role != "conformance_evidence"
            or ref.uri != self._path(name).as_uri()
            or ref.media_type != "application/json"
            or ref.format != "json"
        ):
            raise ValueError("sealed conformance artifact reference is invalid")
        raw = read_regular(self._objects_fd, name, immutable=True)
        if hashlib.sha256(raw).hexdigest() != ref.digest or len(raw) != ref.size_bytes:
            raise ValueError("sealed conformance artifact digest disagrees")
        try:
            result = PassportProbeResult.model_validate_json(raw, strict=True)
        except Exception as exc:
            raise ValueError("sealed conformance artifact is invalid") from exc
        if raw != canonical_json(result.model_dump(mode="json")):
            raise ValueError("sealed conformance artifact is not canonical")
        self._verify()
        return result

    def _verify(self) -> None:
        _same_inode(self._root_stat, self.root.lstat(), "evidence root substituted")
        _same_inode(
            self._base_stat,
            os.stat("conformance_evidence", dir_fd=self._root_fd, follow_symlinks=False),
            "evidence directory substituted",
        )
        _same_inode(
            self._objects_stat,
            os.stat("objects", dir_fd=self._base_fd, follow_symlinks=False),
            "evidence objects directory substituted",
        )

    def _path(self, name: str) -> Path:
        return self.root / "conformance_evidence" / "objects" / name

    def close(self) -> None:
        for name in ("_objects_fd", "_base_fd", "_root_fd"):
            fd = getattr(self, name, -1)
            if fd >= 0:
                try:
                    os.close(fd)
                except OSError:
                    pass
                setattr(self, name, -1)

    def __del__(self) -> None:
        self.close()


__all__ = ["SealedProbeStore"]
