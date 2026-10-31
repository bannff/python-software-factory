"""Artifact verification helpers for the local durable dataset store."""

from __future__ import annotations

import json
from pathlib import Path

from .adapters.scenario_store import LocalScenarioPackStore
from .atomic_io import read_bytes_no_follow
from .contracts import DatasetArtifactRef, DatasetGenerationRequest, DatasetManifest
from .helpers import _file_uri, _sha256
from .recipe import path_from_uri
from .scenario_generation import validate_scenario_lineage_against_pack
from .artifact_checks import (
    _blueprint_lineage_matches, _has_routing_shape, _scenario_request_matches,
    _verify_declared_rows, _verify_non_empty_record_dataset, _verify_routing_views,
    require_artifact_path, verify_manifest_path,
)


def verify_artifact(
    artifact: DatasetArtifactRef,
    manifests_dir: Path,
    artifacts_root: Path,
    request: DatasetGenerationRequest | None = None,
    expected_job_id: str | None = None,
) -> None:
    """Verify a stored artifact reference before exposing it publicly."""
    dataset_path = path_from_uri(artifact.dataset_uri)
    reference_path = dataset_path.with_suffix(".ref.json")
    require_artifact_path(dataset_path, reference_path, artifacts_root)
    if (expected_job_id is not None
            and dataset_path.resolve().parent != (artifacts_root.resolve() / expected_job_id)):
        raise ValueError("Dataset artifact does not belong to this job")
    dataset_content = read_bytes_no_follow(dataset_path)
    if _sha256(dataset_content) != artifact.digest:
        raise ValueError("Dataset artifact digest does not match its reference")
    manifest_path = path_from_uri(artifact.manifest_uri)
    try:
        manifest_content = read_bytes_no_follow(manifest_path)
    except FileNotFoundError:
        raise ValueError("Dataset manifest is missing") from None
    verify_manifest_path(manifest_path, artifact.manifest_uri, manifests_dir)
    manifest = DatasetManifest.model_validate_json(manifest_content)
    if expected_job_id is not None and manifest.provenance.job_id != expected_job_id:
        raise ValueError("Dataset manifest provenance does not belong to this job")
    manifest_declares_schema = "record_schema" in manifest.model_fields_set
    artifact_declares_schema = "record_schema" in artifact.model_fields_set
    if manifest_declares_schema != artifact_declares_schema:
        raise ValueError("Dataset record schema declaration differs across artifact and manifest")
    _verify_non_empty_record_dataset(dataset_content, manifest)
    if manifest.scenario_lineage is not None:
        records = [
            json.loads(line) for line in read_bytes_no_follow(dataset_path).splitlines()
            if line.strip()
        ]
        pack = LocalScenarioPackStore(
            artifacts_root.parent, create=False,
        ).load(manifest.scenario_lineage.scenario_pack)
        validate_scenario_lineage_against_pack(
            records, manifest.scenario_lineage, pack,
        )
    if (
        manifest.dataset_uri != artifact.dataset_uri
        or manifest.dataset_digest != artifact.digest
        or manifest.training_uri != artifact.training_uri
        or manifest.schema_version != artifact.schema_version
        or (manifest_declares_schema and manifest.record_schema != artifact.record_schema)
        or manifest.training_views != artifact.available_views
        or manifest.view_schema_versions != artifact.view_schema_versions
    ):
        raise ValueError("Dataset manifest does not match its artifact reference")
    if not _blueprint_lineage_matches(manifest, artifacts_root.parent):
        raise ValueError("Dataset manifest blueprint lineage failed verification")
    if request is not None and (
        manifest.recipe_uri != request.recipe_uri
        or manifest.recipe_digest != request.recipe_digest
        or manifest.input_artifacts != request.input_artifacts
        or manifest.context_snapshot.uri != request.context_snapshot.uri
        or manifest.context_snapshot.digest != request.context_snapshot.digest
        or manifest.tool_schema_snapshot.uri != request.tool_schema_snapshot.uri
        or manifest.tool_schema_snapshot.digest != request.tool_schema_snapshot.digest
        or manifest.execution_policy != request.execution_policy
        or manifest.training_views != request.requested_views
        or manifest.blueprint_binding != request.blueprint_binding
        or manifest.approval_binding != request.approval_binding
        or not _scenario_request_matches(manifest, request)
    ):
        raise ValueError("Dataset manifest does not match the submitted request")
    declared_schema = manifest.record_schema if manifest_declares_schema else None
    if request is not None:
        from .recipe import resolve_recipe

        recipe_schema = resolve_recipe(request).record_schema
        if declared_schema is not None and recipe_schema != declared_schema:
            raise ValueError("Dataset record schema does not match verified recipe")
        effective_schema = recipe_schema
    else:
        effective_schema = declared_schema
    if effective_schema is not None:
        _verify_declared_rows(dataset_content, effective_schema)
    if effective_schema != "edge_routing_example" and _has_routing_shape(dataset_content):
        raise ValueError("Routing-shaped dataset rows have a non-routing record schema")
    if effective_schema == "edge_routing_example":
        _verify_routing_views(dataset_content, dataset_path, artifact)
        if not manifest.quality_results.passed:
            raise ValueError("Routing artifact quality and trusted provenance did not pass")
        from .quality_edge_routing import evaluate_edge_routing_quality
        from .validation import validate_edge_routing_records

        records = list(validate_edge_routing_records(
            json.loads(line) for line in dataset_content.splitlines() if line.strip()
        ))
        actual_quality = evaluate_edge_routing_quality(records)
        if not actual_quality.passed or actual_quality != manifest.quality_results:
            raise ValueError("Routing artifact quality and trusted provenance did not pass")
    elif effective_schema == "edge_sensor_window":
        if request is not None and manifest.allowed_local_roots != request.allowed_local_roots:
            raise ValueError("Dataset manifest local-root policy does not match the request")
        from .quality import evaluate_quality

        records = [
            json.loads(line) for line in dataset_content.splitlines() if line.strip()
        ]
        allowed_local_roots = (
            request.allowed_local_roots if request is not None
            else manifest.allowed_local_roots
        )
        actual_quality = evaluate_quality(
            records,
            record_schema="edge_sensor_window",
            allowed_local_roots=allowed_local_roots,
        )
        if not actual_quality.passed or actual_quality != manifest.quality_results:
            raise ValueError("Edge sensor artifact payload quality failed verification")
    if effective_schema != "edge_routing_example" and artifact.training_uri:
        training_path = path_from_uri(artifact.training_uri)
        if _sha256(read_bytes_no_follow(training_path)) != artifact.digest:
            raise ValueError("Training view does not match the dataset artifact")
