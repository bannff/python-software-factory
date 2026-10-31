"""Authoring-only acquisition of the one approved immutable Chronos-2 backbone."""
from __future__ import annotations

import uuid
from pathlib import Path
from urllib.parse import unquote, urlparse

from pydantic import Field, ValidationInfo, field_validator

from .authoring_policy import require_authoring
from .chronos_acquisition_evidence import (
    validate_acquisition_document, write_acquisition_document,
)
from .passport_config import resolve_chronos_roots
from .passport_refs import FrozenModel, PassportArtifactRef
from .passport_tree_seal import (
    remove_staging_tree, require_read_only_tree, seal_read_only_tree,
)
from .passport_trees import chronos_backbone_artifact_ref, verify_model_tree_artifact_ref
from .adapters.chronos_identity import (
    MODEL_ID, MODEL_REVISION, acquisition_package_versions,
)
from .adapters.chronos_pipeline import (
    acquire_training_pipeline, load_local_pipeline, save_backbone,
)


class PackageEvidence(FrozenModel):
    """Bounded installed-package evidence captured with an acquisition."""

    name: str = Field(min_length=1, max_length=64)
    version: str = Field(min_length=1, max_length=128)


class ChronosBackboneAcquisitionReceipt(FrozenModel):
    """Immutable receipt for the exact locally sealed Chronos-2 backbone."""

    artifact: PassportArtifactRef
    model_id: str = Field(min_length=1, max_length=128)
    model_revision: str = Field(min_length=40, max_length=64)
    packages: tuple[PackageEvidence, ...] = Field(min_length=1, max_length=8)

    @field_validator("artifact")
    @classmethod
    def _artifact(
        cls, value: PassportArtifactRef, info: ValidationInfo,
    ) -> PassportArtifactRef:
        context = info.context or {}
        validate_chronos_backbone_ref(value, context.get("storage_root"))
        return value


def acquire_chronos2_backbone(
    storage_root: str | Path,
) -> ChronosBackboneAcquisitionReceipt:
    """Acquire, smoke-load locally, and seal the approved Hub revision."""
    require_authoring()
    roots = resolve_chronos_roots(storage_root)
    root = roots.backbone_root
    staging = root / f".acquire-{uuid.uuid4().hex}"
    try:
        pipeline = acquire_training_pipeline()
        save_backbone(pipeline, staging)
        write_acquisition_document(staging, pipeline)
        load_local_pipeline(staging)
        provisional = chronos_backbone_artifact_ref("backbone", staging, root)
        destination = root / provisional.digest
        if destination.exists():
            existing = chronos_backbone_artifact_ref("backbone", destination, root)
            validate_chronos_backbone_ref(existing, roots.trust_root)
            if existing.digest != provisional.digest:
                raise ValueError("Chronos backbone content-address collision")
            remove_staging_tree(staging)
        else:
            seal_read_only_tree(staging)
            staging.rename(destination)
        artifact = chronos_backbone_artifact_ref("backbone", destination, root)
        validate_chronos_backbone_ref(artifact, roots.trust_root)
        packages = tuple(
            PackageEvidence(name=name, version=value)
            for name, value in sorted(acquisition_package_versions().items())
        )
        return ChronosBackboneAcquisitionReceipt.model_validate(
            {
                "artifact": artifact, "model_id": MODEL_ID,
                "model_revision": MODEL_REVISION, "packages": packages,
            },
            context={"storage_root": roots.trust_root},
        )
    except Exception:
        remove_staging_tree(staging)
        raise


def validate_chronos_backbone_ref(
    ref: PassportArtifactRef, storage_root: str | Path | None = None,
) -> None:
    """Require the exact approved role, format, media type, identity and revision."""
    expected = {
        "role": "backbone", "format": "chronos2-backbone",
        "media_type": "application/vnd.amazon.chronos2.backbone",
        "identity": MODEL_ID, "version": MODEL_REVISION,
    }
    if any(getattr(ref, key) != value for key, value in expected.items()):
        raise ValueError("Chronos local backbone ref does not match the approved identity")
    roots = resolve_chronos_roots(storage_root)
    trust_root = roots.trust_root
    parsed = urlparse(ref.uri)
    if parsed.scheme != "file" or parsed.netloc or parsed.query or parsed.fragment:
        raise ValueError("Chronos local backbone requires an exact file URI")
    path = Path(unquote(parsed.path))
    namespace = trust_root / "backbones" / "chronos-2"
    try:
        if path.resolve().parent != namespace.resolve() or path.name != ref.digest:
            raise ValueError
    except (OSError, ValueError) as exc:
        raise ValueError(
            "Chronos local backbone is outside the authoritative digest namespace"
        ) from exc
    verify_model_tree_artifact_ref(ref, trust_root)
    validate_acquisition_document(path)
    require_read_only_tree(path)


__all__ = [
    "ChronosBackboneAcquisitionReceipt", "PackageEvidence",
    "acquire_chronos2_backbone", "validate_chronos_backbone_ref",
]
