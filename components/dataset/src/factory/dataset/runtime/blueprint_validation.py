"""Fail-closed DatasetBlueprint validation against registered immutable refs."""
from __future__ import annotations

from pathlib import Path

from .adapters.scenario_store import LocalScenarioPackStore
from .blueprint_catalog import SCENARIO_RECIPE_URI
from .blueprint_codec import blueprint_binding
from .blueprint_models import DatasetBlueprint
from .blueprint_results import DatasetBlueprintValidation
from .ports import DatasetQualityPolicyPort, DatasetReferenceRegistryPort


class DatasetBlueprintValidator:
    def __init__(
        self, storage_root: Path, registry: DatasetReferenceRegistryPort,
        quality_policies: DatasetQualityPolicyPort,
    ) -> None:
        self._packs = LocalScenarioPackStore(storage_root, create=False)
        self._registry = registry
        self._quality_policies = quality_policies

    def validate(self, blueprint: DatasetBlueprint) -> DatasetBlueprintValidation:
        resolution = self._registry.validate(blueprint)
        self._quality_policies.require(blueprint.quality_policy)
        evidence = blueprint.source_evidence[0]
        pack = self._packs.load(evidence.artifact)
        rule = pack.generation_rule
        if (
            rule.adapter != resolution.generator_adapter
            or rule.version != resolution.generator_version
        ):
            raise ValueError("ScenarioPack generation rule does not match capability reference")
        return DatasetBlueprintValidation(
            binding=blueprint_binding(blueprint),
            recipe_uri=resolution.recipe_uri,
            stage_names=resolution.stage_names,
            record_schema="generic",
        )


def require_submission_authority(request, storage_root: Path) -> None:
    """Fail closed for the registered human-gated materialization route."""
    if request.recipe_uri != SCENARIO_RECIPE_URI:
        return
    binding = request.blueprint_binding
    authority = request.approval_binding
    if binding is None or authority is None:
        raise ValueError("Registered scenario generation requires blueprint and approval bindings")
    if (
        authority.blueprint_digest != binding.digest
        or authority.quality_policy != binding.quality_policy
    ):
        raise ValueError("Dataset approval binding does not match its blueprint binding")

    from .adapters.blueprint_config import (
        ConfiguredHumanApprovalRegistry, ConfiguredQualityPolicyRegistry,
    )
    from .adapters.blueprint_store import LocalBlueprintStore
    from .blueprint_catalog import FixtureReferenceRegistry
    from .blueprint_snapshots import blueprint_snapshot_specs
    from .contracts import DatasetExecutionPolicy

    blueprint = LocalBlueprintStore(storage_root).load(binding)
    resolution = FixtureReferenceRegistry().validate(blueprint)
    ConfiguredQualityPolicyRegistry.from_environment().require(
        blueprint.quality_policy,
    )
    ConfiguredHumanApprovalRegistry.from_environment().require(
        authority.approval, binding.digest, blueprint.quality_policy,
    )
    context_spec, tool_spec = blueprint_snapshot_specs(
        storage_root, blueprint, binding,
    )
    evidence = blueprint.source_evidence[0].artifact
    generation = request.scenario_generation
    expected_input = [(evidence.uri, evidence.digest, "scenario_pack")]
    actual_input = [
        (item.uri, item.digest, item.artifact_role) for item in request.input_artifacts
    ]
    if (
        authority.quality_policy != blueprint.quality_policy
        or request.recipe_digest != blueprint.recipe.digest
        or request.schema_version != blueprint.output_schema.version
        or tuple(request.requested_views) != blueprint.requested_views
        or request.execution_policy != DatasetExecutionPolicy()
        or request.context_snapshot != context_spec[0]
        or request.tool_schema_snapshot != tool_spec[0]
        or request.idempotency_key != f"dataset-blueprint:{binding.digest}"
        or actual_input != expected_input
        or generation is None
        or generation.scenario_pack != evidence
        or generation.generator_adapter != resolution.generator_adapter
        or generation.generator_version != resolution.generator_version
        or generation.seed != blueprint.generation_seed
    ):
        raise ValueError("Dataset generation request does not match its authority bindings")
