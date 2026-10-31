"""Public runtime facade for immutable definition artifacts."""
from __future__ import annotations

from pathlib import Path

from .adapters.definition_store import LocalDefinitionArtifactStore
from .definition_codec import DEFAULT_DEFINITION_MAX_BYTES
from .definition_models import (
    DefinitionArtifact, DefinitionArtifactPublishResult, DefinitionArtifactRef,
)


def dataset_publish_definition_artifact(
    artifact: DefinitionArtifact, storage_root: Path | None = None,
    max_size_bytes: int = DEFAULT_DEFINITION_MAX_BYTES,
) -> DefinitionArtifactPublishResult:
    """Canonically and exclusively publish one stable definition revision."""
    return LocalDefinitionArtifactStore(
        storage_root or Path(".dataset_store"), max_size_bytes,
    ).publish(artifact)


def dataset_resolve_definition_artifact(
    ref: DefinitionArtifactRef, storage_root: Path | None = None,
    max_size_bytes: int = DEFAULT_DEFINITION_MAX_BYTES,
) -> DefinitionArtifact:
    """Resolve and fully verify one immutable definition reference."""
    return LocalDefinitionArtifactStore(
        storage_root or Path(".dataset_store"), max_size_bytes,
    ).resolve(ref)


__all__ = [
    "dataset_publish_definition_artifact", "dataset_resolve_definition_artifact",
]
