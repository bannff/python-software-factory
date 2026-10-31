"""Concrete nested public payload DTOs for Dataset MCP results."""
from __future__ import annotations

from typing import Literal

from pydantic import Field, StrictInt, StrictStr

from .base import OutputDTO


class DigestEvidenceOutput(OutputDTO):
    sha256: StrictStr


class ArtifactVersionReferenceOutput(OutputDTO):
    uri: StrictStr
    digest: StrictStr
    version: StrictStr


class ArtifactReferenceOutput(OutputDTO):
    uri: StrictStr
    sha256: StrictStr
    evidence: DigestEvidenceOutput


class StageReceiptOutput(OutputDTO):
    job_id: StrictStr
    dataset_uri: StrictStr
    manifest_uri: StrictStr
    digest: StrictStr


class ArtifactMapEntryOutput(OutputDTO):
    job_id: StrictStr
    dataset_ref: ArtifactReferenceOutput
    manifest_ref: ArtifactReferenceOutput
    contract_ref: ArtifactReferenceOutput


class PreparedCanOutput(OutputDTO):
    contract_artifact: StrictStr
    x_3d_artifact: StrictStr
    x_2d_artifact: StrictStr
    y_artifact: StrictStr
    timespans_artifact: StrictStr | None = None
    n_samples: StrictInt
    window_size: StrictInt
    n_features: StrictInt
    label_dist: dict[StrictStr, StrictInt]


class TrainingBundleOutput(OutputDTO):
    schema_version: Literal["1.0"] | None = None
    top_can_ids: list[StrictStr] | None = None
    source_digests: list[StrictStr] | None = None
    prior_data_policy_ref: ArtifactVersionReferenceOutput | None = None
    signal_schema_refs_by_can_id: dict[StrictStr, ArtifactVersionReferenceOutput] | None = None
    prepared_by_can_id: dict[StrictStr, PreparedCanOutput]
    vehicle_id: StrictStr | None = None
    augmented_dataset: ArtifactReferenceOutput | None = None
    augmented_manifest: ArtifactReferenceOutput | None = None
    context_refs: dict[StrictStr, ArtifactReferenceOutput] | None = None
    training_artifacts_by_can_id: dict[StrictStr, dict[StrictStr, ArtifactReferenceOutput]] | None = None
    failure_pattern_artifacts: dict[StrictStr, StrictStr] | None = None
    failure_scenario_refs: dict[StrictStr, "ScenarioReferenceOutput"] | None = None
    augmented_dataset_artifact: StrictStr | None = None
    augmented_manifest_artifact: StrictStr | None = None
    context_artifacts: dict[StrictStr, StrictStr] | None = None


class ScenarioReferenceOutput(OutputDTO):
    identity: StrictStr
    version: StrictStr
    uri: StrictStr
    digest: StrictStr


class LegacyStageOutput(OutputDTO):
    job_id: StrictStr
    n_mf4: StrictInt | None = None


class ContractArtifactOutput(OutputDTO):
    job_id: StrictStr
    uri: StrictStr
    digest: StrictStr


class LegacyProjectionOutput(OutputDTO):
    ingest: LegacyStageOutput
    profile: LegacyStageOutput
    contract_artifacts: dict[StrictStr, ContractArtifactOutput]
    synthesize: LegacyStageOutput
    window: LegacyStageOutput
    augment: LegacyStageOutput
    top_can_ids: list[StrictStr]
    context: dict[StrictStr, LegacyStageOutput] | None = None
    context_artifacts: dict[StrictStr, StrictStr] | None = None


class DbcProvenanceOutput(OutputDTO):
    source_url: StrictStr
    artifact_uri: StrictStr
    source_kind: Literal["approved_manifest", "explicit_local"]
    spdx_license: StrictStr
    retrieved_at: StrictStr
    sha256: StrictStr
    parser_name: StrictStr
    parser_version: StrictStr
    validation_status: Literal["approved", "validated"]


class DbcDefinitionOutput(OutputDTO):
    definition_id: StrictStr
    catalog_id: StrictStr
    version: StrictStr
    digest: StrictStr
    provenance: DbcProvenanceOutput


class DbcSelectionOutput(OutputDTO):
    catalog_id: StrictStr
    catalog_version: StrictStr
    vehicle_alias: StrictStr
    vehicle_make: StrictStr
    vehicle_model: StrictStr
    vehicle_year: StrictInt | None = None
    message_fingerprints: list["FingerprintOutput"]


class FingerprintOutput(OutputDTO):
    arbitration_id: StrictInt
    dlc: StrictInt
    is_extended: bool


class PipelineStageOutput(OutputDTO):
    stage: StrictStr
    recipe: StrictStr | None = None
    optional: bool | None = None
    outputs: list[StrictStr] | None = None


class PipelineParametersOutput(OutputDTO):
    vehicle_id: StrictStr
    storage_root: StrictStr
    max_samples: StrictInt
    config_overrides: dict = Field(default_factory=dict)
    use_context: bool
    context_sources: list[StrictStr]
    emit_timespans: bool


class PipelineIdempotencyOutput(OutputDTO):
    equal_retry: StrictStr
    divergent_retry: StrictStr


class PipelineReturnsOutput(OutputDTO):
    status: StrictStr
    artifacts: StrictStr
    training_bundle: StrictStr
    legacy_projection: StrictStr
