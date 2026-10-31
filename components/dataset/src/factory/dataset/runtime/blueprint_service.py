"""Human-gated translation from a validated blueprint to the existing job request."""
from __future__ import annotations

from pathlib import Path

from .adapters.blueprint_store import LocalBlueprintStore
from .approval_models import DatasetApprovalBinding
from .atomic_io import atomic_write_immutable
from .blueprint_models import (
    BlueprintResolution, DatasetBlueprint, DatasetHumanApprovalRef,
)
from .blueprint_snapshots import blueprint_snapshot_specs
from .blueprint_results import DatasetBlueprintPublishResult
from .contracts import (
    DatasetGenerationRequest, DatasetInputRef,
)
from .ports import (
    DatasetBlueprintStorePort, DatasetHumanApprovalPort,
    DatasetReferenceRegistryPort,
)
from .scenario_models import ScenarioPackGenerationInput


class DatasetBlueprintService:
    def __init__(
        self, storage_root: Path, registry: DatasetReferenceRegistryPort,
        approvals: DatasetHumanApprovalPort,
        store: DatasetBlueprintStorePort | None = None,
    ) -> None:
        self._root = storage_root.resolve()
        self._registry = registry
        self._approvals = approvals
        self._store = store or LocalBlueprintStore(self._root)

    def prepare(
        self, blueprint: DatasetBlueprint, approval: DatasetHumanApprovalRef,
        binding,
    ) -> tuple[DatasetBlueprintPublishResult, DatasetGenerationRequest | None]:
        resolution: BlueprintResolution = self._registry.validate(blueprint)
        self._approvals.require(
            approval, binding.digest, blueprint.quality_policy,
        )
        approval_binding = DatasetApprovalBinding(
            approval=approval, blueprint_digest=binding.digest,
            quality_policy=blueprint.quality_policy,
        )
        published = self._store.publish(blueprint)
        if published.status == "conflict":
            return published, None
        context, tools = self._snapshots(blueprint, binding)
        evidence = blueprint.source_evidence[0]
        request = DatasetGenerationRequest(
            recipe_uri=resolution.recipe_uri,
            recipe_digest=blueprint.recipe.digest,
            input_artifacts=[DatasetInputRef(
                uri=evidence.artifact.uri, digest=evidence.artifact.digest,
                artifact_role="scenario_pack",
            )],
            context_snapshot=context,
            tool_schema_snapshot=tools,
            requested_views=list(blueprint.requested_views),
            scenario_generation=ScenarioPackGenerationInput(
                scenario_pack=evidence.artifact,
                generator_adapter=resolution.generator_adapter,
                generator_version=resolution.generator_version,
                seed=blueprint.generation_seed,
            ),
            idempotency_key=f"dataset-blueprint:{binding.digest}",
            schema_version=blueprint.output_schema.version,
            blueprint_binding=binding,
            approval_binding=approval_binding,
        )
        return published, request

    def _snapshots(self, blueprint, binding):
        context_spec, tool_spec = blueprint_snapshot_specs(
            self._root, blueprint, binding,
        )
        context, context_path, context_content = context_spec
        tools, tool_path, tool_content = tool_spec
        atomic_write_immutable(context_path, context_content)
        atomic_write_immutable(tool_path, tool_content)
        return context, tools
