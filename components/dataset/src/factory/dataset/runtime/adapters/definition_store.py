"""Rooted, symlink-resistant immutable local definition artifact adapter."""
from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import unquote, urlsplit

from ..atomic_io import atomic_create_immutable, read_bytes_no_follow
from ..definition_codec import (
    DEFAULT_DEFINITION_MAX_BYTES, canonical_definition_bytes,
    definition_digest, parse_definition_bytes, require_max_size,
)
from ..definition_models import (
    DefinitionArtifact, DefinitionArtifactConflict,
    DefinitionArtifactIntegrityError, DefinitionArtifactPublishResult,
    DefinitionArtifactRef,
)


class LocalDefinitionArtifactStore:
    """One exclusive canonical file per stable logical identity and version."""

    def __init__(
        self, storage_root: Path, max_size_bytes: int = DEFAULT_DEFINITION_MAX_BYTES,
    ) -> None:
        root = Path(os.path.abspath(storage_root.expanduser()))
        self.root = root / "definition_artifacts" / "identities"
        self.max_size_bytes = require_max_size(max_size_bytes)

    def publish(self, artifact: DefinitionArtifact) -> DefinitionArtifactPublishResult:
        content = canonical_definition_bytes(artifact)
        if len(content) > self.max_size_bytes:
            raise ValueError("definition artifact exceeds configured max size on publish")
        path = self._artifact_path(artifact.identity, artifact.version)
        self._reject_symlinks(path)
        requested = self._reference(artifact, content, path)
        try:
            created = atomic_create_immutable(path, content)
        except OSError as error:
            raise DefinitionArtifactIntegrityError(
                "definition artifact path is not safe"
            ) from error
        if created:
            self.resolve(requested)
            return DefinitionArtifactPublishResult(status="published", ref=requested)
        existing, existing_content = self._load_path(path)
        if (existing.identity, existing.version) != (artifact.identity, artifact.version):
            raise DefinitionArtifactIntegrityError(
                "definition artifact identity/version path is inconsistent"
            )
        existing_ref = self._reference(existing, existing_content, path)
        if existing_content == content:
            return DefinitionArtifactPublishResult(status="existing", ref=existing_ref)
        return DefinitionArtifactPublishResult(
            status="conflict",
            conflict=DefinitionArtifactConflict(
                identity=artifact.identity, version=artifact.version,
                existing_digest=existing_ref.digest,
                requested_digest=requested.digest,
            ),
        )

    def resolve(self, ref: DefinitionArtifactRef) -> DefinitionArtifact:
        path = self._checked_path(ref)
        artifact, content = self._load_path(path)
        if len(content) != ref.size_bytes:
            raise DefinitionArtifactIntegrityError("definition artifact size mismatch")
        if definition_digest(content) != ref.digest:
            raise DefinitionArtifactIntegrityError("definition artifact digest mismatch")
        expected = (ref.schema_name, ref.schema_version, ref.identity, ref.version)
        actual = (
            artifact.schema_name, artifact.schema_version,
            artifact.identity, artifact.version,
        )
        if actual != expected:
            raise DefinitionArtifactIntegrityError(
                "definition artifact schema or identity/version mismatch"
            )
        return artifact

    def _load_path(self, path: Path) -> tuple[DefinitionArtifact, bytes]:
        self._reject_symlinks(path)
        try:
            content = read_bytes_no_follow(path, max_bytes=self.max_size_bytes)
            return parse_definition_bytes(content, self.max_size_bytes), content
        except (OSError, ValueError) as error:
            raise DefinitionArtifactIntegrityError(
                "definition artifact failed bounded verification"
            ) from error

    def _checked_path(self, ref: DefinitionArtifactRef) -> Path:
        parsed = urlsplit(ref.uri)
        decoded = unquote(parsed.path)
        if (
            parsed.scheme != "file" or parsed.netloc not in {"", "localhost"}
            or parsed.query or parsed.fragment or ".." in Path(decoded).parts
        ):
            raise DefinitionArtifactIntegrityError("definition artifact URI is unsafe")
        expected = self._artifact_path(ref.identity, ref.version)
        supplied = Path(os.path.abspath(decoded))
        if supplied != expected or ref.uri != expected.as_uri():
            raise DefinitionArtifactIntegrityError(
                "definition artifact URI escapes its rooted identity path"
            )
        return expected

    def _artifact_path(self, identity: str, version: str) -> Path:
        return self.root / identity / f"{version}.json"

    @staticmethod
    def _reference(
        artifact: DefinitionArtifact, content: bytes, path: Path,
    ) -> DefinitionArtifactRef:
        return DefinitionArtifactRef(
            schema_name=artifact.schema_name, schema_version=artifact.schema_version,
            identity=artifact.identity, version=artifact.version, uri=path.as_uri(),
            digest=definition_digest(content), size_bytes=len(content),
        )

    @staticmethod
    def _reject_symlinks(path: Path) -> None:
        current = Path(path.anchor)
        for part in path.parts[1:]:
            current /= part
            if current.is_symlink():
                raise DefinitionArtifactIntegrityError(
                    "definition artifact path contains a symlink"
                )


__all__ = ["LocalDefinitionArtifactStore"]
