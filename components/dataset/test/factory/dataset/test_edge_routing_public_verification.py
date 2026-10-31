"""Routing split mechanics and fail-closed publication boundaries."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from factory.dataset.runtime.artifact_utils import _verify_routing_views, verify_artifact
from factory.dataset.runtime.bundle_writer import (
    _routing_view_contents, _training_view_name, write_bundle,
)
from factory.dataset.runtime.contracts import (
    DatasetArtifactRef, DatasetGenerationRequest, DatasetManifest,
    DatasetProvenanceRecord, DatasetQualityResults, DatasetRecipe,
    DatasetSnapshotRef, DatasetToolSchemaSnapshotRef,
)
from factory.dataset.runtime.edge_routing_contracts import EdgeRoutingExample
from factory.dataset.runtime.local import LocalDatasetStore
from factory.dataset.runtime.quality import evaluate_quality
from factory.dataset.runtime.recipe import records_content

from .test_edge_routing_views import _synthetic_forgery
from .test_edge_routing_contracts import _example

from .test_edge_routing_views import _records
from .test_edge_routing_views import _request

@pytest.mark.parametrize("downgraded_schema", ["conversation", "generic"])
def test_public_verifier_rejects_routing_schema_downgrade(
    tmp_path: Path, downgraded_schema: str,
) -> None:
    store, artifact, dataset_path = _synthetic_forgery(tmp_path)
    full_view = dataset_path.parent / f"view-train-{artifact.digest}.jsonl"
    full_view.write_bytes(dataset_path.read_bytes())
    original_manifest = DatasetManifest.model_validate_json(
        Path(artifact.manifest_uri.removeprefix("file://")).read_bytes(),
    )
    forged_manifest = original_manifest.model_copy(update={
        "record_schema": downgraded_schema,
        "training_uri": full_view.resolve().as_uri(),
        "training_views": ["train"],
        "view_schema_versions": {"train": "1.0"},
    })
    content = forged_manifest.model_dump_json(exclude_none=True).encode()
    manifest_path = store.manifests_dir / f"manifest-{hashlib.sha256(content).hexdigest()}.json"
    manifest_path.write_bytes(content)
    forged = artifact.model_copy(update={
        "manifest_uri": manifest_path.resolve().as_uri(),
        "record_schema": downgraded_schema,
        "training_uri": full_view.resolve().as_uri(),
        "available_views": ["train"],
        "view_schema_versions": {"train": "1.0"},
    })
    with pytest.raises(ValueError, match="record schema|routing-shaped"):
        verify_artifact(forged, store.manifests_dir, store.artifacts_dir)

def test_public_verifier_binds_artifact_and_manifest_schema(tmp_path: Path) -> None:
    store, artifact, _ = _synthetic_forgery(tmp_path)
    manifest = DatasetManifest.model_validate_json(
        Path(artifact.manifest_uri.removeprefix("file://")).read_bytes(),
    )
    downgraded = manifest.model_copy(update={"record_schema": "generic"})
    content = downgraded.model_dump_json(exclude_none=True).encode()
    path = store.manifests_dir / f"manifest-{hashlib.sha256(content).hexdigest()}.json"
    path.write_bytes(content)
    forged = artifact.model_copy(update={"manifest_uri": path.resolve().as_uri()})
    with pytest.raises(ValueError, match="record schema|manifest"):
        verify_artifact(forged, store.manifests_dir, store.artifacts_dir)

def test_public_verifier_binds_record_schema_to_verified_recipe(tmp_path: Path) -> None:
    recipe_path = tmp_path / "routing-recipe.json"
    recipe_content = json.dumps({
        "version": "routing-v1", "stages": [{"name": "local-validate"}],
        "record_schema": "edge_routing_example",
    }).encode()
    recipe_path.write_bytes(recipe_content)
    request = _request(["default"]).model_copy(update={
        "recipe_uri": recipe_path.resolve().as_uri(),
        "recipe_digest": hashlib.sha256(recipe_content).hexdigest(),
    })
    store = LocalDatasetStore(tmp_path / "store")
    records = [{"messages": [
        {"role": "user", "content": "request"},
        {"role": "assistant", "content": "response"},
    ]}]
    artifact = write_bundle(
        store, records, request,
        DatasetRecipe(version="generic-v1", stages=[{"name": "local-validate"}],
                      record_schema="generic"),
        "schema-forgery", {}, [], evaluate_quality(records),
        DatasetProvenanceRecord(materializer="test", job_id="schema-forgery"), None,
    )
    with pytest.raises(ValueError, match="record schema does not match verified recipe"):
        verify_artifact(artifact, store.manifests_dir, store.artifacts_dir, request=request)

def test_generic_labeled_outcome_row_is_not_mistaken_for_routing(tmp_path: Path) -> None:
    store = LocalDatasetStore(tmp_path / "store")
    records = [{
        "record_id": "item-1", "split": "train", "outcome": "resolved",
        "messages": [
            {"role": "user", "content": "status"},
            {"role": "assistant", "content": "resolved"},
        ],
    }]
    artifact = write_bundle(
        store, records, _request(["default"]),
        DatasetRecipe(version="generic-v1", stages=[{"name": "local-validate"}],
                      record_schema="generic"),
        "generic-outcome", {}, [], evaluate_quality(records),
        DatasetProvenanceRecord(materializer="test", job_id="generic-outcome"), None,
    )
    verify_artifact(artifact, store.manifests_dir, store.artifacts_dir)

def test_verifier_rejects_rows_inconsistent_with_declared_schema(tmp_path: Path) -> None:
    store = LocalDatasetStore(tmp_path / "store")
    records = [{"value": 1}]
    quality = DatasetQualityResults(checks={"record_count": "passed: 1"})
    artifact = write_bundle(
        store, records, _request(["default"]),
        DatasetRecipe(version="generic-v1", stages=[{"name": "local-validate"}],
                      record_schema="generic"),
        "forged-conversation", {}, [], quality,
        DatasetProvenanceRecord(materializer="test", job_id="forged-conversation"), None,
    )
    manifest = DatasetManifest.model_validate_json(
        Path(artifact.manifest_uri.removeprefix("file://")).read_bytes(),
    ).model_copy(update={"record_schema": "conversation"})
    content = manifest.model_dump_json(exclude_none=True).encode()
    path = store.manifests_dir / f"manifest-{hashlib.sha256(content).hexdigest()}.json"
    path.write_bytes(content)
    forged = artifact.model_copy(update={
        "record_schema": "conversation", "manifest_uri": path.resolve().as_uri(),
    })
    with pytest.raises(ValueError, match="declared record schema"):
        verify_artifact(forged, store.manifests_dir, store.artifacts_dir)

@pytest.mark.parametrize("schema", ["generic", "can_frame", "can_artifact"])
def test_legacy_bundle_without_schema_field_remains_readable(
    tmp_path: Path, schema: str,
) -> None:
    store = LocalDatasetStore(tmp_path / "store")
    records = [{"signal": "example"}]
    artifact = write_bundle(
        store, records, _request(["default"]),
        DatasetRecipe(version="legacy-v1", stages=[{"name": "local-validate"}],
                      record_schema=schema),
        "legacy", {}, [], DatasetQualityResults(checks={"record_count": "passed: 1"}),
        DatasetProvenanceRecord(materializer="test", job_id="legacy"), None,
    )
    manifest_data = json.loads(Path(artifact.manifest_uri.removeprefix("file://")).read_bytes())
    manifest_data.pop("record_schema")
    manifest_content = json.dumps(manifest_data, separators=(",", ":")).encode()
    manifest_path = store.manifests_dir / (
        f"manifest-{hashlib.sha256(manifest_content).hexdigest()}.json"
    )
    manifest_path.write_bytes(manifest_content)
    artifact_data = artifact.model_dump(mode="json", exclude={"record_schema"})
    artifact_data["manifest_uri"] = manifest_path.resolve().as_uri()
    legacy = DatasetArtifactRef.model_validate(artifact_data)
    assert "record_schema" not in legacy.model_fields_set
    verify_artifact(legacy, store.manifests_dir, store.artifacts_dir)

def test_schema_omission_cannot_hide_routing_rows(tmp_path: Path) -> None:
    store, artifact, dataset_path = _synthetic_forgery(tmp_path)
    full_view = dataset_path.parent / f"view-train-{artifact.digest}.jsonl"
    full_view.write_bytes(dataset_path.read_bytes())
    manifest_data = json.loads(Path(artifact.manifest_uri.removeprefix("file://")).read_bytes())
    manifest_data.pop("record_schema")
    manifest_data["training_uri"] = full_view.resolve().as_uri()
    manifest_data["training_views"] = ["train"]
    manifest_data["view_schema_versions"] = {"train": "1.0"}
    content = json.dumps(manifest_data, separators=(",", ":")).encode()
    path = store.manifests_dir / f"manifest-{hashlib.sha256(content).hexdigest()}.json"
    path.write_bytes(content)
    artifact_data = artifact.model_dump(mode="json", exclude={"record_schema"})
    artifact_data.update({
        "manifest_uri": path.resolve().as_uri(),
        "training_uri": full_view.resolve().as_uri(),
        "available_views": ["train"],
        "view_schema_versions": {"train": "1.0"},
    })
    hidden = DatasetArtifactRef.model_validate(artifact_data)
    with pytest.raises(ValueError, match="Routing-shaped"):
        verify_artifact(hidden, store.manifests_dir, store.artifacts_dir)
