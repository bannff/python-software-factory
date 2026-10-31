"""Strict DTOs for Dataset CAN terminal, intelligence, and projection tools."""
from __future__ import annotations

from typing import Literal
from pydantic import Field, StrictBool, StrictInt, StrictStr, field_validator, model_validator

from .base import InputDTO, OutputDTO, validate_strict_json
from .nested import (
    ArtifactMapEntryOutput, ArtifactReferenceOutput, ContractArtifactOutput,
    DbcDefinitionOutput,
    DbcProvenanceOutput, DbcSelectionOutput, FingerprintOutput, LegacyProjectionOutput,
    LegacyStageOutput, PipelineIdempotencyOutput, PipelineParametersOutput, PipelineReturnsOutput,
    PipelineStageOutput, StageReceiptOutput, TrainingBundleOutput,
)
from ...runtime.dbc_models import DbcCandidateScore, MessageFingerprint
from ...runtime.dbc_semantics import DbcVersionDefinition
from ...runtime.failure_pattern_models import FailurePatternRef, FailurePatternSpec


class CanFingerprintInput(InputDTO):
    arbitration_id: StrictInt = Field(ge=0, le=0x1FFFFFFF)
    dlc: StrictInt = Field(ge=0, le=64)
    is_extended: StrictBool = False


class FailurePatternRefInput(InputDTO):
    pattern_id: StrictStr
    version: StrictStr
    digest: StrictStr


class CanTerminalInput(InputDTO):
    attempt_id: StrictStr
    mf4_dir: StrictStr
    dbc_path: StrictStr | None = None
    vehicle_id: StrictStr = "unknown"
    dbc_catalog_id: StrictStr = ""
    dbc_catalog_version: StrictStr = ""
    vehicle_alias: StrictStr = ""
    vehicle_make: StrictStr = ""
    vehicle_model: StrictStr = ""
    vehicle_year: StrictInt | None = None
    message_fingerprints: list[CanFingerprintInput | MessageFingerprint] | None = None
    failure_pattern_refs: list[FailurePatternRefInput] | None = None
    storage_root: StrictStr | None = None
    max_samples: StrictInt = 20_000
    config_overrides: dict[StrictStr, object] | None = None
    use_context: StrictBool = False
    context_sources: list[StrictStr] | None = None
    emit_timespans: StrictBool = False

    @field_validator("config_overrides")
    @classmethod
    def _nested_config_is_strict(cls, value: dict[str, object] | None) -> dict[str, object] | None:
        return validate_strict_json(value)


class DbcCatalogInput(InputDTO):
    storage_root_override: StrictStr | None = None


class ResolveDbcCandidateInput(InputDTO):
    catalog_id: StrictStr = ""
    version: StrictStr = ""
    vehicle_alias: StrictStr = ""
    vehicle_make: StrictStr = ""
    vehicle_model: StrictStr = ""
    vehicle_year: StrictInt | None = None
    message_fingerprints: list[CanFingerprintInput | MessageFingerprint] | None = None
    threshold: StrictInt = 10
    storage_root_override: StrictStr | None = None


class FailurePatternInput(InputDTO):
    pattern_id: StrictStr
    version: StrictStr = ""


class ProjectCanGraphInput(InputDTO):
    dataset_uri: StrictStr
    graph_backend: StrictStr = ""


class EmptyInput(InputDTO):
    pass


class CanTerminalOutput(OutputDTO):
    """Discriminated CAN terminal payload for completed, conflict, or failed attempts."""

    schema_version: Literal["1.0"]
    status: Literal["completed", "conflict", "failed"]
    attempt_id: StrictStr
    request_sha256: StrictStr
    error: StrictStr | None = None
    existing_request_sha256: StrictStr | None = None
    vehicle_id: StrictStr | None = None
    artifacts: dict[StrictStr, ArtifactReferenceOutput] | None = None
    artifact_map: dict[StrictStr, ArtifactMapEntryOutput] | None = None
    stage_receipts: dict[StrictStr, StageReceiptOutput] | None = None
    training_bundle: TrainingBundleOutput | None = None
    legacy_projection: LegacyProjectionOutput | None = None
    ingest: LegacyStageOutput | None = None
    profile: LegacyStageOutput | None = None
    contract_artifacts: dict[StrictStr, ContractArtifactOutput] | None = None
    synthesize: LegacyStageOutput | None = None
    window: LegacyStageOutput | None = None
    augment: LegacyStageOutput | None = None
    top_can_ids: list[StrictStr] | None = None
    context: dict[StrictStr, LegacyStageOutput] | None = None
    context_artifacts: dict[StrictStr, StrictStr] | None = None
    dbc_selection: DbcSelectionOutput | None = None
    dbc_definition: DbcDefinitionOutput | None = None
    failure_pattern_refs: list[FailurePatternRef] | None = None

    @model_validator(mode="after")
    def _terminal_shape(self) -> "CanTerminalOutput":
        if self.status == "completed" and (self.error is not None or self.training_bundle is None):
            raise ValueError("completed CAN terminal requires training_bundle and no error")
        if self.status == "conflict" and (self.error is None or self.existing_request_sha256 is None):
            raise ValueError("conflict CAN terminal requires error and existing request digest")
        if self.status == "failed" and self.error is None:
            raise ValueError("failed CAN terminal requires error")
        return self


class VehicleAliasesOutput(OutputDTO):
    make: StrictStr
    model: StrictStr
    years: list[StrictInt]
    aliases: list[StrictStr]


class DbcCatalogEntryOutput(OutputDTO):
    catalog_id: StrictStr
    version: StrictStr
    provenance: DbcProvenanceOutput
    vehicle: VehicleAliasesOutput
    message_fingerprints: list[FingerprintOutput]
    artifact_status: Literal["verified", "rejected"] | None = None


class DbcCatalogErrorOutput(OutputDTO):
    catalog_id: StrictStr
    version: StrictStr
    error: StrictStr


class DbcCatalogOutput(OutputDTO):
    entries: list[DbcCatalogEntryOutput]
    count: StrictInt
    errors: list[DbcCatalogErrorOutput]


class DbcCandidateOutput(OutputDTO):
    status: Literal["resolved", "ambiguous", "not_found"]
    threshold: StrictInt
    selected: DbcCatalogEntryOutput | None = None
    candidates: list[DbcCandidateScore] = []
    errors: list[StrictStr] = []
    definition: DbcVersionDefinition | None = None
    artifact_path: StrictStr | None = None


class FailurePatternListOutput(OutputDTO):
    patterns: list[FailurePatternRef]
    count: StrictInt


class FailurePatternOutput(FailurePatternSpec):
    pass


class CanGraphProjectionOutput(OutputDTO):
    status: Literal["completed"]
    dataset_uri: StrictStr
    record_count: StrictInt
    entity_ids: list[StrictStr]
    entity_count: StrictInt


class CanPipelineOverviewOutput(OutputDTO):
    tool_name: StrictStr
    mcp_server: StrictStr
    category: StrictStr
    owner: StrictStr
    stages: list[PipelineStageOutput]
    description: StrictStr
    required_parameters: list[StrictStr]
    optional_parameters: PipelineParametersOutput
    idempotency: PipelineIdempotencyOutput
    returns: PipelineReturnsOutput


CanTerminalOutput.model_rebuild()
DbcCatalogOutput.model_rebuild()
DbcCandidateOutput.model_rebuild()
FailurePatternListOutput.model_rebuild()
FailurePatternOutput.model_rebuild()
CanPipelineOverviewOutput.model_rebuild()
