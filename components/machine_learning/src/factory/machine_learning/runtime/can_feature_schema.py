"""Neutral projections of Dataset-issued CAN policy and schema artifacts."""
from .can_artifact_refs import (
    CanDatasetArtifactRef,
    CanPriorPolicyProjection,
    CanSignalSchemaProjection,
    load_prior_policy,
    load_signal_schema,
    ref_from_uri,
)


def dataset_artifact_ref(result: dict, version: str = "1.0") -> CanDatasetArtifactRef:
    """Build the canonical body-digest ref from a completed Dataset stage."""
    ref = ref_from_uri(str(result["dataset_uri"]))
    if version != ref.version:
        raise ValueError("Dataset artifact version mismatch")
    return ref


__all__ = [
    "CanDatasetArtifactRef", "CanPriorPolicyProjection",
    "CanSignalSchemaProjection", "dataset_artifact_ref", "load_prior_policy",
    "load_signal_schema",
]
