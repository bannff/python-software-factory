"""In-process registry of named training datasets.

Process-local like the base-model registry: it survives a request, not a restart.
Revision-fenced so two UI tabs cannot silently overwrite each other.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, replace
from pathlib import Path
from threading import Lock
from typing import Iterable

from factory.mcp_utils.interface import TypedToolFailure

from .models import DatasetTrainingInput

ID_PATTERN = re.compile(r"^[a-z][a-z0-9_-]{1,63}$")
_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")


@dataclass(frozen=True)
class DatasetRecord:
    dataset_id: str
    uri: str
    manifest_uri: str
    digest: str
    view_name: str
    view_schema_version: str
    description: str
    revision: int = 1


def _local_path(uri: str) -> Path | None:
    path = Path(uri.removeprefix("file://"))
    return path if path.is_file() else None


def verify_digest(uri: str, digest: str) -> None:
    """Reject a malformed digest, or one that disagrees with a local file's content."""
    if not _DIGEST.match(digest):
        raise TypedToolFailure("dataset_digest_mismatch", "digest must be sha256:<64 hex>")
    local = _local_path(uri)
    if local is None:
        return  # remote URIs cannot be hashed here; the trainer verifies on load
    hasher = hashlib.sha256()
    with local.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            hasher.update(chunk)
    if f"sha256:{hasher.hexdigest()}" != digest:
        raise TypedToolFailure("dataset_digest_mismatch", uri)


class DatasetRegistry:
    def __init__(self) -> None:
        self._items: dict[str, DatasetRecord] = {}
        self._lock = Lock()

    def register(self, record: DatasetRecord) -> DatasetRecord:
        if not ID_PATTERN.match(record.dataset_id):
            raise TypedToolFailure("dataset_invalid", "dataset name must match ^[a-z][a-z0-9_-]{1,63}$")
        verify_digest(record.uri, record.digest)
        with self._lock:
            if record.dataset_id in self._items:
                raise TypedToolFailure("dataset_exists", record.dataset_id)
            self._items[record.dataset_id] = record
        return record

    def get(self, dataset_id: str) -> DatasetRecord:
        record = self._items.get(dataset_id)
        if record is None:
            raise TypedToolFailure("dataset_not_found", dataset_id)
        return record

    def list(self) -> list[DatasetRecord]:
        return sorted(self._items.values(), key=lambda r: r.dataset_id)

    def update(self, dataset_id: str, expected_revision: int, description: str) -> DatasetRecord:
        with self._lock:
            current = self.get(dataset_id)
            if current.revision != expected_revision:
                raise TypedToolFailure("dataset_revision_conflict", dataset_id)
            updated = replace(current, description=description, revision=current.revision + 1)
            self._items[dataset_id] = updated
        return updated

    def delete(self, dataset_id: str, used_uris: Iterable[str]) -> None:
        with self._lock:
            record = self.get(dataset_id)
            if record.uri in set(used_uris):
                raise TypedToolFailure("dataset_in_use", dataset_id)
            del self._items[dataset_id]


REGISTRY = DatasetRegistry()


def resolve_training_input(
    dataset_id: str | None, uri: str | None, manifest_uri: str | None, digest: str | None,
    view_name: str | None, view_schema_version: str | None,
) -> DatasetTrainingInput:
    """Build trainer input from a registered ``dataset_id`` or the explicit fields.

    The trainer takes a bare 64-hex digest; registered digests carry ``sha256:``.
    """
    if dataset_id is not None:
        rec = REGISTRY.get(dataset_id)
        uri, manifest_uri, digest = rec.uri, rec.manifest_uri, rec.digest
        view_name, view_schema_version = rec.view_name, rec.view_schema_version
    fields = (uri, manifest_uri, digest, view_name, view_schema_version)
    if any(f is None for f in fields):
        raise ValueError("pass dataset_id or all of the dataset fields")
    return DatasetTrainingInput(
        dataset_uri=uri, manifest_uri=manifest_uri,
        dataset_digest=digest.removeprefix("sha256:"),
        view_name=view_name, view_schema_version=view_schema_version,
    )
