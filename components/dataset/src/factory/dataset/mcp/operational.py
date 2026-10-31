"""Stateful MCP tools for dataset job submission and observation."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from factory.mcp_utils.interface import ToolResult, operational

from ..interface import (
    dataset_cancel_job,
    dataset_get_job,
    dataset_publish_scenario_pack,
    dataset_submit_generation,
)
from ..runtime.base import DatasetSnapshotRef, DatasetToolSchemaSnapshotRef
from ..runtime.local_inputs import canonicalize_local_input
from .contracts.lifecycle import (
    CancelJobInput,
    GenerationOutput,
    JobInput,
    JobOutput,
    PublishScenarioPackInput,
    SubmitGenerationInput,
)
from .contracts.scenario_outputs import ScenarioPackOutput


def register(mcp: Any, storage_root: Path | None = None) -> None:
    """Register operational dataset generation tools."""
    registered_root = storage_root

    def selected_root(override: str | None) -> Path | None:
        return Path(override) if override is not None else registered_root

    @mcp.tool(name="dataset_publish_scenario_pack")
    @operational(input_model=PublishScenarioPackInput, output_model=ScenarioPackOutput)
    def publish_scenario_pack(
        draft_json: str, storage_root: str | None = None,
    ) -> ToolResult[ScenarioPackOutput]:
        """Validate and publish a ScenarioPack from canonical draft JSON."""
        from ..runtime.scenario_models import ScenarioPackDraft
        draft = ScenarioPackDraft.model_validate_json(draft_json)
        return dataset_publish_scenario_pack(draft, selected_root(storage_root)).model_dump(mode="json")

    @mcp.tool(name="dataset_submit_generation")
    @operational(input_model=SubmitGenerationInput, output_model=GenerationOutput)
    def submit_generation(
        recipe_uri: str, recipe_digest: str, context_snapshot_uri: str,
        context_snapshot_digest: str, tool_schema_snapshot_uri: str,
        tool_schema_snapshot_digest: str, *, allowed_tools: list[str] | None = None,
        input_artifact_uris: list[str] | None = None,
        input_artifact_digests: list[str] | None = None,
        input_artifact_roles: list[str] | None = None,
        allowed_local_roots: list[str] | None = None,
        scenario_pack_identity: str | None = None,
        scenario_pack_version: str | None = None, scenario_pack_uri: str | None = None,
        scenario_pack_digest: str | None = None, generator_adapter: str | None = None,
        generator_version: str | None = None, generation_seed: int | None = None,
        requested_views: str | None = None, fail_closed: bool = True,
        retry_from_checkpoint_only: bool = True, idempotency_key: str | None = None,
        schema_version: str = "1.0", storage_root: str | None = None,
    ) -> ToolResult[GenerationOutput]:
        """Accept a flat generation request and return its durable job receipt."""
        from ..runtime.contracts import (
            DatasetExecutionPolicy,
            DatasetGenerationRequest,
            DatasetInputRef,
        )
        from ..runtime.scenario_models import ScenarioPackGenerationInput, ScenarioPackRef
        context_snapshot = DatasetSnapshotRef(uri=context_snapshot_uri, digest=context_snapshot_digest)
        tool_snapshot = DatasetToolSchemaSnapshotRef(
            uri=tool_schema_snapshot_uri, digest=tool_schema_snapshot_digest,
            allowed_tools=allowed_tools or [],
        )
        uris, digests, roles = input_artifact_uris or [], input_artifact_digests or [], input_artifact_roles
        if len(uris) != len(digests):
            raise ValueError("input_artifact_uris and input_artifact_digests must have equal lengths")
        if roles is not None and len(roles) != len(uris):
            raise ValueError("input_artifact_roles must match input artifact lengths")
        input_artifacts = [DatasetInputRef(
            uri=canonicalize_local_input(uri), digest=digest,
            artifact_role=roles[index] if roles is not None else None,
        ) for index, (uri, digest) in enumerate(zip(uris, digests, strict=True))]
        views = [value.strip() for value in requested_views.split(",") if value.strip()] if requested_views else ["default"]
        values = (scenario_pack_identity, scenario_pack_version, scenario_pack_uri,
                  scenario_pack_digest, generator_adapter, generator_version, generation_seed)
        if any(value is not None for value in values) and not all(value is not None for value in values):
            raise ValueError("Scenario generation fields must be supplied together")
        scenario_generation = None
        if all(value is not None for value in values):
            scenario_generation = ScenarioPackGenerationInput(
                scenario_pack=ScenarioPackRef(identity=scenario_pack_identity, version=scenario_pack_version,
                                               uri=canonicalize_local_input(scenario_pack_uri), digest=scenario_pack_digest),
                generator_adapter=generator_adapter, generator_version=generator_version, seed=generation_seed,
            )
        request = DatasetGenerationRequest(
            recipe_uri=recipe_uri, recipe_digest=recipe_digest, input_artifacts=input_artifacts,
            allowed_local_roots=allowed_local_roots or (),
            context_snapshot=context_snapshot, tool_schema_snapshot=tool_snapshot,
            requested_views=views, execution_policy=DatasetExecutionPolicy(
                fail_closed=fail_closed, retry_from_checkpoint_only=retry_from_checkpoint_only),
            scenario_generation=scenario_generation, idempotency_key=idempotency_key,
            schema_version=schema_version,
        )
        return dataset_submit_generation(request, selected_root(storage_root)).model_dump(mode="json")

    @mcp.tool(name="dataset_get_job")
    @operational(input_model=JobInput, output_model=JobOutput)
    def get_job(job_id: str, storage_root: str | None = None) -> ToolResult[JobOutput]:
        """Return status, optionally selecting a caller-owned store root."""
        status = dataset_get_job(job_id, selected_root(storage_root))
        return status.model_dump(mode="json") if status else None

    @mcp.tool(name="dataset_cancel_job")
    @operational(input_model=CancelJobInput, output_model=JobOutput)
    def cancel_job(
        job_id: str, reason: str = "cancelled", storage_root: str | None = None,
    ) -> ToolResult[JobOutput]:
        """Cancel a job within the caller-selected store root."""
        return dataset_cancel_job(job_id, reason, selected_root(storage_root)).model_dump(mode="json")
