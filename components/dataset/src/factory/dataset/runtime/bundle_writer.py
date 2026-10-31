"""Bundle writing for materialized dataset views."""

from __future__ import annotations

import re

from .contracts import (
    DatasetArtifactRef,
    DatasetFallbackRecord,
    DatasetGenerationRequest,
    DatasetManifest,
    DatasetProvenanceRecord,
    DatasetQualityResults,
    DatasetStageCheckpoint,
)
from .helpers import _file_uri, _now, _sha256, _write_immutable
from .recipe import records_content

_ROUTING_VIEWS = frozenset({"train", "validation", "test"})


def _routing_view_contents(records: list, requested_views: list[str]) -> dict[str, bytes]:
    """Build disjoint split bytes before any routing bundle path is written."""
    from .edge_routing_contracts import EdgeRoutingExample

    requested = set(requested_views)
    if "train" not in requested or not requested.issubset(_ROUTING_VIEWS):
        raise ValueError("Routing views must include train and use only train/validation/test")
    routing_records = [EdgeRoutingExample.model_validate(record) for record in records]
    views: dict[str, bytes] = {}
    for split in requested_views:
        selected = [record for record in routing_records if record.split == split]
        if not selected:
            raise ValueError(f"Routing views require records in requested {split} split")
        views[split] = records_content(selected, record_schema="edge_routing_example")
    return views


def _training_view_name(record_schema: str, requested_views: list[str]) -> str:
    return "train" if record_schema == "edge_routing_example" else requested_views[0]


def write_bundle(
    store,
    records,
    request: DatasetGenerationRequest,
    recipe,
    job_id: str,
    stage_versions: dict[str, str],
    stage_lineage: list[DatasetStageCheckpoint],
    final_quality_results: DatasetQualityResults,
    final_provenance: DatasetProvenanceRecord,
    final_fallback: DatasetFallbackRecord | None,
) -> DatasetArtifactRef:
    """Write immutable dataset, views, manifest, and sidecar."""
    routing_views: dict[str, bytes] = {}
    if recipe.record_schema == "edge_sensor_window":
        from .quality import evaluate_quality

        actual_quality = evaluate_quality(
            records,
            record_schema="edge_sensor_window",
            allowed_local_roots=request.allowed_local_roots,
        )
        if not actual_quality.passed or actual_quality != final_quality_results:
            raise ValueError("Edge sensor bundle quality changed before publication")
    if recipe.record_schema == "edge_routing_example":
        from .quality import evaluate_quality

        actual_quality = evaluate_quality(records, record_schema="edge_routing_example")
        if not actual_quality.passed or actual_quality != final_quality_results:
            raise ValueError("Routing bundle quality and trusted provenance must pass")
        routing_views = _routing_view_contents(records, request.requested_views)
    source_content = records_content(records, record_schema=recipe.record_schema)
    dataset_digest = _sha256(source_content)
    bundle_dir = store.artifacts_dir / job_id
    bundle_dir.mkdir(exist_ok=True)
    suffix = ".json" if recipe.record_schema == "can_artifact" else ".jsonl"
    dataset_path = bundle_dir / f"dataset-{dataset_digest}{suffix}"
    _write_immutable(dataset_path, source_content)
    available_views: list[str] = []
    view_schema_versions: dict[str, str] = {}
    training_uri = ""
    for requested_view in request.requested_views:
        view_name = re.sub(r"[^A-Za-z0-9_.-]", "_", requested_view)
        view_content = routing_views.get(requested_view, source_content)
        view_digest = _sha256(view_content)
        view_path = bundle_dir / f"view-{view_name}-{view_digest}{suffix}"
        _write_immutable(view_path, view_content)
        available_views.append(requested_view)
        view_schema_versions[requested_view] = recipe.schema_version
        if requested_view == _training_view_name(recipe.record_schema, request.requested_views):
            training_uri = _file_uri(view_path)
    artifact = DatasetArtifactRef(
        dataset_uri=_file_uri(dataset_path),
        manifest_uri="",
        digest=dataset_digest,
        schema_version=recipe.schema_version,
        record_schema=recipe.record_schema,
        available_views=available_views,
        view_schema_versions=view_schema_versions,
        training_uri=training_uri,
    )
    blueprint_lineage = None
    if request.blueprint_binding is not None:
        from .adapters.blueprint_store import LocalBlueprintStore
        from .blueprint_codec import blueprint_lineage as build_blueprint_lineage
        blueprint = LocalBlueprintStore(store.root).load(request.blueprint_binding)
        blueprint_lineage = build_blueprint_lineage(blueprint, request.blueprint_binding)
    manifest = DatasetManifest(
        schema_version=recipe.schema_version,
        record_schema=recipe.record_schema,
        dataset_uri=artifact.dataset_uri,
        dataset_digest=artifact.digest,
        recipe_uri=request.recipe_uri,
        recipe_digest=request.recipe_digest,
        input_artifacts=request.input_artifacts,
        allowed_local_roots=request.allowed_local_roots,
        context_snapshot=request.context_snapshot,
        tool_schema_snapshot=request.tool_schema_snapshot,
        execution_policy=request.execution_policy,
        training_views=available_views,
        view_schema_versions=view_schema_versions,
        training_uri=training_uri,
        quality_results=final_quality_results,
        provenance=final_provenance,
        stage_adapter_versions=stage_versions or {"local-recipe": "1"},
        stage_lineage=stage_lineage,
        blueprint_binding=request.blueprint_binding,
        approval_binding=request.approval_binding,
        blueprint_lineage=blueprint_lineage,
        scenario_lineage=next(
            (item.scenario_lineage for item in reversed(stage_lineage)
             if item.scenario_lineage is not None),
            None,
        ),
        fallback=final_fallback,
        created_at=_now(),
    )
    manifest_content = manifest.model_dump_json(exclude_none=True).encode()
    manifest_path = store.manifests_dir / f"manifest-{_sha256(manifest_content)}.json"
    _write_immutable(manifest_path, manifest_content)
    artifact = artifact.model_copy(update={"manifest_uri": _file_uri(manifest_path)})
    _write_immutable(
        dataset_path.with_suffix(".ref.json"),
        artifact.model_dump_json(exclude_none=True).encode(),
    )
    return artifact
