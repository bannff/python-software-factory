"""Content-addressed immutable DatasetBlueprint storage."""
from __future__ import annotations

from contextlib import contextmanager
import fcntl
import hashlib
import os
from pathlib import Path
from typing import Iterator

from ..atomic_io import (
    atomic_write_immutable, open_file_no_follow, read_bytes_no_follow,
)
from ..blueprint_codec import blueprint_binding, canonical_json
from ..blueprint_models import DatasetBlueprint, DatasetBlueprintBinding, DatasetBlueprintRef
from ..blueprint_results import DatasetBlueprintConflict, DatasetBlueprintPublishResult


class LocalBlueprintStore:
    def __init__(self, storage_root: Path) -> None:
        self.root = storage_root.resolve() / "blueprints"
        self.content_dir = self.root / "sha256"
        self.identity_dir = self.root / "identities"
        self.lock_dir = self.root / "locks"
        self.content_dir.mkdir(parents=True, exist_ok=True)
        self.identity_dir.mkdir(parents=True, exist_ok=True)
        self.lock_dir.mkdir(parents=True, exist_ok=True)

    def publish(self, blueprint: DatasetBlueprint) -> DatasetBlueprintPublishResult:
        binding = blueprint_binding(blueprint)
        requested = DatasetBlueprintRef(
            identity=binding.identity, version=binding.version,
            uri=(self.content_dir / f"{binding.digest}.json").resolve().as_uri(),
            digest=binding.digest,
        )
        index_path = self._identity_path(binding)
        with self._identity_lock(binding):
            try:
                existing = self._read_ref(index_path)
            except FileNotFoundError:
                existing = None
            if existing is not None:
                return self._existing(existing, requested)
            self._write_exclusive(
                self._content_path(binding.digest), canonical_json(blueprint),
            )
            created = self._write_exclusive(index_path, canonical_json(requested))
            if not created:
                return self._existing(self._read_ref(index_path), requested)
            self.load(binding)
            return DatasetBlueprintPublishResult(status="published", ref=requested)

    @contextmanager
    def _identity_lock(
        self, binding: DatasetBlueprintBinding,
    ) -> Iterator[None]:
        identity = f"{binding.identity}\0{binding.version}".encode()
        path = self.lock_dir / f"{hashlib.sha256(identity).hexdigest()}.lock"
        atomic_write_immutable(path, b"")
        descriptor = open_file_no_follow(path, os.O_RDONLY)
        with os.fdopen(descriptor, "a+b") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    def load(self, binding: DatasetBlueprintBinding) -> DatasetBlueprint:
        path = self._content_path(binding.digest)
        try:
            content = read_bytes_no_follow(path)
            blueprint = DatasetBlueprint.model_validate_json(content)
        except (OSError, ValueError) as error:
            raise ValueError("DatasetBlueprint artifact failed verification") from error
        if canonical_json(blueprint) != content or blueprint_binding(blueprint) != binding:
            raise ValueError("DatasetBlueprint artifact does not match its binding")
        return blueprint

    def _existing(
        self, existing: DatasetBlueprintRef, requested: DatasetBlueprintRef,
    ) -> DatasetBlueprintPublishResult:
        expected_uri = self._content_path(existing.digest).resolve().as_uri()
        if (
            existing.identity != requested.identity
            or existing.version != requested.version
            or existing.uri != expected_uri
        ):
            raise ValueError("DatasetBlueprint identity reference is invalid")
        binding = DatasetBlueprintBinding(
            identity=existing.identity, version=existing.version,
            digest=existing.digest,
            quality_policy=self._load_policy(existing.digest),
        )
        self.load(binding)
        if existing.digest != requested.digest:
            return DatasetBlueprintPublishResult(status="conflict", conflict=DatasetBlueprintConflict(
                identity=requested.identity, version=requested.version,
                existing_digest=existing.digest, requested_digest=requested.digest,
            ))
        return DatasetBlueprintPublishResult(status="existing", ref=existing)

    def _load_policy(self, digest: str):
        return DatasetBlueprint.model_validate_json(
            read_bytes_no_follow(self._content_path(digest))
        ).quality_policy

    def _content_path(self, digest: str) -> Path:
        return self.content_dir / f"{digest}.json"

    def _identity_path(self, binding: DatasetBlueprintBinding) -> Path:
        return self.identity_dir / f"{binding.identity}@{binding.version}.ref.json"

    @staticmethod
    def _read_ref(path: Path) -> DatasetBlueprintRef:
        content = read_bytes_no_follow(path)
        ref = DatasetBlueprintRef.model_validate_json(content)
        if canonical_json(ref) != content:
            raise ValueError("DatasetBlueprint identity reference is not canonical")
        return ref

    @staticmethod
    def _write_exclusive(path: Path, content: bytes) -> bool:
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            descriptor = open_file_no_follow(
                path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o444,
            )
        except FileExistsError:
            if read_bytes_no_follow(path) != content:
                raise
            return False
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        return True
