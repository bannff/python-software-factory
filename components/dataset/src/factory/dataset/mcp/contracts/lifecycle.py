"""Strict DTOs for Dataset generation, artifacts, and scenario-pack MCP tools."""
from __future__ import annotations

from typing import ClassVar, Literal

from pydantic import Field, StrictBool, StrictInt, StrictStr

from ...runtime.approval_models import DatasetApprovalBinding
from ...runtime.blueprint_models import DatasetBlueprintBinding
from ...runtime.contracts import (
    DatasetExecutionPolicy,
    DatasetInputRef,
    DatasetProvenanceRecord,
    DatasetQualityResults,
    DatasetSnapshotRef,
    DatasetToolSchemaSnapshotRef,
)
from .base import InputDTO, OutputDTO
from .nested import ArtifactReferenceOutput
from .resolved_artifact import ResolvedArtifactOutput
from .scenario_outputs import (
    ScenarioAssumptionOutput,
    ScenarioLineageOutput,
    ScenarioPackOutput,
    ScenarioPackRefOutput,
    ScenarioSourceOutput,
)


class PublishScenarioPackInput(InputDTO):
    draft_json: StrictStr
    storage_root: StrictStr | None = None


class SubmitGenerationInput(InputDTO):
    preserve_domain_schema_version: ClassVar[bool] = True
    recipe_uri: StrictStr
    recipe_digest: StrictStr
    context_snapshot_uri: StrictStr
    context_snapshot_digest: StrictStr
    tool_schema_snapshot_uri: StrictStr
    tool_schema_snapshot_digest: StrictStr
    allowed_tools: list[StrictStr] | None = None
    input_artifact_uris: list[StrictStr] | None = None
    input_artifact_digests: list[StrictStr] | None = None
    input_artifact_roles: list[StrictStr] | None = None
    allowed_local_roots: list[StrictStr] = Field(
        default_factory=list,
        description="Absolute local roots authorized for edge sensor payload reads.",
    )
    scenario_pack_identity: StrictStr | None = None
    scenario_pack_version: StrictStr | None = None
    scenario_pack_uri: StrictStr | None = None
    scenario_pack_digest: StrictStr | None = None
    generator_adapter: StrictStr | None = None
    generator_version: StrictStr | None = None
    generation_seed: StrictInt | None = None
    requested_views: StrictStr | None = None
    fail_closed: StrictBool = True
    retry_from_checkpoint_only: StrictBool = True
    idempotency_key: StrictStr | None = None
    schema_version: Literal["1.0"] = "1.0"
    storage_root: StrictStr | None = None


class JobInput(InputDTO):
    job_id: StrictStr
    storage_root: StrictStr | None = None


class CancelJobInput(JobInput):
    reason: StrictStr = "cancelled"


class ScenarioPackInput(InputDTO):
    identity: StrictStr
    version: StrictStr
    uri: StrictStr
    digest: StrictStr
    storage_root: StrictStr | None = None


class DatasetUriInput(InputDTO):
    dataset_uri: StrictStr
    storage_root: StrictStr | None = None


class GenerationOutput(OutputDTO):
    job_id: StrictStr
    status: Literal["queued"] | None = None
    submitted_at: StrictStr | None = None


class ArtifactOutput(OutputDTO):
    allows_null: ClassVar[bool] = True
    dataset_uri: StrictStr | None = None
    manifest_uri: StrictStr | None = None
    digest: StrictStr | None = None
    schema_version: StrictStr | None = None
    record_schema: Literal[
        "conversation", "can_frame", "can_artifact", "generic",
        "edge_sensor_window", "edge_routing_example",
    ] | None = None
    available_views: list[StrictStr] | None = None
    view_schema_versions: dict[StrictStr, StrictStr] | None = None
    training_uri: StrictStr | None = None


class InputArtifactOutput(OutputDTO):
    uri: StrictStr
    digest: StrictStr
    artifact_role: StrictStr | None = None


class SnapshotOutput(OutputDTO):
    uri: StrictStr
    digest: StrictStr


class ToolSchemaSnapshotOutput(SnapshotOutput):
    allowed_tools: list[StrictStr]


class ExecutionPolicyOutput(OutputDTO):
    fail_closed: StrictBool
    retry_from_checkpoint_only: StrictBool
    allowed_fallbacks: list[StrictStr]


class ScenarioGenerationOutput(OutputDTO):
    scenario_pack: ScenarioPackRefOutput
    generator_adapter: StrictStr
    generator_version: StrictStr
    seed: StrictInt


class GenerationRequestOutput(OutputDTO):
    recipe_uri: StrictStr
    recipe_digest: StrictStr
    input_artifacts: list[InputArtifactOutput]
    allowed_local_roots: list[StrictStr]
    context_snapshot: SnapshotOutput
    tool_schema_snapshot: ToolSchemaSnapshotOutput
    requested_views: list[StrictStr]
    execution_policy: ExecutionPolicyOutput
    scenario_generation: ScenarioGenerationOutput | None = None
    blueprint_binding: DatasetBlueprintBinding | None = None
    approval_binding: DatasetApprovalBinding | None = None
    idempotency_key: StrictStr | None = None
    schema_version: StrictStr
    context_snapshot_uri: StrictStr
    context_snapshot_digest: StrictStr
    tool_schema_snapshot_uri: StrictStr
    tool_schema_snapshot_digest: StrictStr


class JobOutput(OutputDTO):
    allows_null: ClassVar[bool] = True
    job_id: StrictStr | None = None
    status: Literal["queued", "running", "completed", "failed"] | None = None
    submitted_at: StrictStr | None = None
    started_at: StrictStr | None = None
    completed_at: StrictStr | None = None
    cancelled_at: StrictStr | None = None
    error: StrictStr | None = None
    artifact: ArtifactOutput | None = None
    request: GenerationRequestOutput | None = None


__all__ = [name for name in globals() if name.endswith(("Input", "Output"))]
