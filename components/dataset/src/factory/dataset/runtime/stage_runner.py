"""Stage execution loop for recipe materialization."""
from __future__ import annotations


from .contracts import (
    DatasetFallbackRecord,
    DatasetGenerationRequest,
    DatasetStageCheckpoint,
    DatasetProvenanceRecord,
    DatasetQualityResults,
)
from .helpers import _config_digest, _sha256
from .stage_helpers import (
    _extract_fallback, _extract_scenario_lineage, _load_checkpoint_records,
    _validate_scenario_stage, require_authorized_fallback,
)
from .ports import DatasetStagePort
from .quality import evaluate_quality
from .recipe import records_content


def run_stage_loop(
    recipe, request: DatasetGenerationRequest, records: list,
    stages: dict[str, DatasetStagePort], checkpoints,
    existing_checkpoints: dict[int, DatasetStageCheckpoint], job_id: str,
    check_running=None,
) -> tuple[list, dict[str, str], DatasetProvenanceRecord, DatasetQualityResults,
           DatasetFallbackRecord | None, list[DatasetStageCheckpoint]]:
    """Execute recipe stages, resuming from checkpoints where possible."""
    record_schema = getattr(recipe, "record_schema", "conversation")
    allowed_local_roots = request.allowed_local_roots
    stage_versions: dict[str, str] = {}
    stage_lineage: list[DatasetStageCheckpoint] = []
    final_quality = evaluate_quality(
        records, record_schema=record_schema,
        allowed_local_roots=allowed_local_roots,
    )
    final_provenance = DatasetProvenanceRecord(materializer="local-recipe", job_id=job_id)
    final_fallback: DatasetFallbackRecord | None = None
    current_content = (
        b"" if record_schema == "can_artifact" and not records
        else records_content(records, record_schema=record_schema)
    )
    current_digest = _sha256(current_content)

    for index, recipe_stage in enumerate(recipe.stages):
        checkpoint = existing_checkpoints.get(index)
        config_digest = _config_digest(recipe_stage.config)
        context_digest = request.context_snapshot.digest
        tool_digest = request.tool_schema_snapshot.digest
        stage_config = dict(recipe_stage.config)
        if recipe_stage.name == "apigenmt":
            stage_config["tool_schema_snapshot"] = request.tool_schema_snapshot
        stage = stages.get(recipe_stage.name)
        if stage is None:
            raise ValueError(f"Unsupported dataset recipe stage: {recipe_stage.name}")

        if checkpoint is not None:
            if (
                checkpoint.stage_name != recipe_stage.name
                or checkpoint.stage_index != index
                or checkpoint.schema_version != recipe.schema_version
                or (
                    request.scenario_generation is not None
                    and checkpoint.adapter_version != stage.stage_version
                )
                or checkpoint.input_digest != current_digest
                or checkpoint.config_digest != config_digest
                or checkpoint.context_snapshot_digest != context_digest
                or checkpoint.tool_schema_snapshot_digest != tool_digest
            ):
                raise ValueError("Stage checkpoint does not match the current job state")
            if checkpoint.fallback is not None:
                require_authorized_fallback(request, checkpoint.fallback)
            records = _load_checkpoint_records(
                checkpoint, record_schema, checkpoints.root, job_id,
                require_digest=request.scenario_generation is not None,
                allowed_local_roots=allowed_local_roots,
            )
            if request.scenario_generation is not None:
                _validate_scenario_stage(
                    stage, records, checkpoint.scenario_lineage,
                    request.scenario_generation,
                )
            stage_versions[recipe_stage.name] = checkpoint.adapter_version
            final_quality = checkpoint.quality_results
            final_provenance = checkpoint.provenance
            final_fallback = checkpoint.fallback or final_fallback
            stage_lineage.append(checkpoint)
            current_digest = checkpoint.output_digest
            continue

        if check_running is not None:
            check_running()
        input_digest = current_digest
        records = list(stage.execute(records, stage_config))
        scenario_lineage = _extract_scenario_lineage(stage)
        if request.scenario_generation is not None:
            _validate_scenario_stage(
                stage, records, scenario_lineage, request.scenario_generation,
            )
        fallback = _extract_fallback(stage, request)
        final_fallback = fallback or final_fallback
        provenance = DatasetProvenanceRecord(materializer="local-recipe", job_id=job_id)
        quality = evaluate_quality(
            records, record_schema=record_schema,
            allowed_local_roots=allowed_local_roots,
        )
        checkpoint = checkpoints.save(
            stage_name=recipe_stage.name, stage_index=index, input_digest=input_digest,
            records=records, schema_version=recipe.schema_version,
            adapter_version=stage.stage_version, config=recipe_stage.config,
            context_snapshot_digest=context_digest,
            tool_schema_snapshot_digest=tool_digest, provenance=provenance,
            quality_results=quality, fallback=fallback, record_schema=record_schema,
            scenario_lineage=scenario_lineage,
            allowed_local_roots=allowed_local_roots,
        )
        final_quality, final_provenance = quality, provenance
        stage_versions[recipe_stage.name] = checkpoint.adapter_version
        stage_lineage.append(checkpoint)
        current_digest = checkpoint.output_digest

    if check_running is not None:
        check_running()
    return (
        records, stage_versions, final_provenance, final_quality,
        final_fallback, stage_lineage,
    )
