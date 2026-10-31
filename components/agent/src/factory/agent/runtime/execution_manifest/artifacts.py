"""Inline-or-Dataset persistence for sealed execution manifests."""
from __future__ import annotations

import os

from .artifact_models import DefinitionArtifact, DefinitionArtifactRef, DefinitionDescriptor
from .canonical import canonical_bytes, sha256, verify_manifest
from .models import ExecutionManifestV1
from .ports import DatasetDefinitionPort

DEFAULT_INLINE_MAX_BYTES = 64 * 1024
DATASET_MAX_BYTES = 1024 * 1024
INLINE_MAX_ENV = "AGENT_EXECUTION_MANIFEST_INLINE_MAX_BYTES"


def inline_max_bytes(value: int | None = None) -> int:
    raw = os.getenv(INLINE_MAX_ENV, str(DEFAULT_INLINE_MAX_BYTES)) if value is None else value
    try:
        limit = int(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError("manifest inline max must be a positive integer") from exc
    if isinstance(raw, bool) or limit <= 0 or limit > DATASET_MAX_BYTES:
        raise ValueError("manifest inline max must be positive and <= Dataset 1 MiB")
    return limit


def manifest_artifact(manifest: ExecutionManifestV1) -> DefinitionArtifact:
    verify_manifest(manifest)
    assert manifest.digest is not None
    return DefinitionArtifact(
        schema_name="agent-execution-manifest", schema_version="1",
        identity=manifest.graph_id, version=manifest.digest.value,
        content=manifest.model_dump(mode="json"),
    )


async def store_manifest(
    manifest: ExecutionManifestV1, port: DatasetDefinitionPort | None = None, *,
    max_inline_bytes: int | None = None,
) -> DefinitionDescriptor:
    artifact = manifest_artifact(manifest)
    raw = canonical_bytes(artifact)
    if len(raw) > DATASET_MAX_BYTES:
        raise ValueError("execution manifest exceeds Dataset 1 MiB maximum")
    if len(raw) <= inline_max_bytes(max_inline_bytes):
        return DefinitionDescriptor(inline=artifact)
    if port is None:
        raise ValueError("Dataset definition port required for over-limit manifest")
    result = await port.publish_definition(raw.decode("utf-8"))
    if result.get("status") == "conflict":
        raise ValueError(f"Dataset definition conflict: {result.get('conflict')}")
    if result.get("status") not in {"published", "existing"}:
        raise RuntimeError(f"Dataset definition publish failed: {result}")
    ref = DefinitionArtifactRef.model_validate(result.get("ref"))
    _verify_reference(ref, artifact, raw)
    return DefinitionDescriptor(reference=ref)


def _verify_reference(
    ref: DefinitionArtifactRef, artifact: DefinitionArtifact, raw: bytes,
) -> None:
    expected = (artifact.schema_name, artifact.schema_version, artifact.identity, artifact.version)
    actual = (ref.schema_name, ref.schema_version, ref.identity, ref.version)
    if actual != expected or ref.digest != sha256(raw).value or ref.size_bytes != len(raw):
        raise ValueError("Dataset definition reference does not bind canonical manifest bytes")


async def resolve_manifest(
    descriptor: DefinitionDescriptor, port: DatasetDefinitionPort | None = None,
) -> ExecutionManifestV1:
    artifact = descriptor.inline
    if descriptor.reference is not None:
        if port is None:
            raise ValueError("Dataset definition port required for referenced manifest")
        ref = descriptor.reference
        resolved = await port.resolve_definition(ref.model_dump(mode="json"))
        artifact = DefinitionArtifact.model_validate(resolved)
        raw = canonical_bytes(artifact)
        _verify_reference(ref, artifact, raw)
    assert artifact is not None
    manifest = ExecutionManifestV1.model_validate_json(canonical_bytes(artifact.content))
    verify_manifest(manifest)
    if artifact.version != manifest.digest.value or artifact.identity != manifest.graph_id:
        raise ValueError("definition artifact identity/version does not bind manifest")
    return manifest


__all__ = [
    "DATASET_MAX_BYTES", "DEFAULT_INLINE_MAX_BYTES", "INLINE_MAX_ENV",
    "inline_max_bytes", "manifest_artifact", "resolve_manifest", "store_manifest",
]
