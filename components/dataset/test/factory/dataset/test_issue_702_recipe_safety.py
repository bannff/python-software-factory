"""Focused recipe and publication safety regressions for GitHub #702."""
from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from factory.dataset.runtime.artifact_utils import verify_artifact
from factory.dataset.runtime.bundle_writer import write_bundle
from factory.dataset.runtime.contracts import (
    DatasetGenerationRequest, DatasetInputRef, DatasetJobStatus,
    DatasetProvenanceRecord, DatasetRecipe, DatasetSnapshotRef,
    DatasetToolSchemaSnapshotRef,
)
from factory.dataset.runtime.local import LocalDatasetMaterializer, LocalDatasetStore
from factory.dataset.runtime.quality import evaluate_quality
from factory.dataset.runtime.recipe import path_from_uri, resolve_recipe


def _snapshot(root: Path, name: str, payload: dict) -> DatasetSnapshotRef:
    content = json.dumps(payload, sort_keys=True).encode()
    digest = hashlib.sha256(content).hexdigest()
    path = root / f"{name}-{digest}.json"
    path.write_bytes(content)
    return DatasetSnapshotRef(uri=path.as_uri(), digest=digest)


def _request(
    root: Path, recipe_uri: str, context: dict, inputs=None,
) -> DatasetGenerationRequest:
    tools = _snapshot(root, "tools", {"allowed_tools": []})
    return DatasetGenerationRequest(
        recipe_uri=recipe_uri,
        recipe_digest=hashlib.sha256(recipe_uri.encode()).hexdigest(),
        input_artifacts=inputs or [],
        context_snapshot=_snapshot(root, "context", context),
        tool_schema_snapshot=DatasetToolSchemaSnapshotRef(
            uri=tools.uri, digest=tools.digest, allowed_tools=[],
        ),
    )


@pytest.mark.parametrize("recipe_uri", [
    "recipe://local/can-pipeline@1",
    "recipe://local/can-pipeline-aug@1",
    "recipe://local/can-pipeline-tax@1",
    "recipe://local/can-pipeline-timegan@1",
])
def test_broken_can_recipes_raise_actionable_migration(
    tmp_path: Path, recipe_uri: str,
) -> None:
    with pytest.raises(ValueError, match=(
        "dataset_materialize_can_training_bundle or explicit single-stage jobs"
    )):
        resolve_recipe(_request(tmp_path, recipe_uri, {}))


def test_broken_recipe_digest_is_verified_before_migration(tmp_path: Path) -> None:
    request = _request(tmp_path, "recipe://local/can-pipeline@1", {})
    request = request.model_copy(update={"recipe_digest": "0" * 64})
    with pytest.raises(ValueError, match="Digest mismatch"):
        resolve_recipe(request)


def test_only_scoped_stage_overrides_are_executable(tmp_path: Path) -> None:
    source = tmp_path / "capture.MF4"
    item = DatasetInputRef(uri=source.as_uri(), digest="a" * 64)
    top_level = resolve_recipe(_request(
        tmp_path, "recipe://local/can-ingest@1",
        {"dbc_path": "/provenance.dbc", "vehicle_id": "provenance"}, [item],
    )).stages[0].config
    assert top_level == {"mf4_paths": [source.as_uri()]}

    scoped = resolve_recipe(_request(
        tmp_path, "recipe://local/can-ingest@1",
        {"dbc_path": "/provenance.dbc", "stage_overrides": {
            "can_ingest": {"dbc_path": "/scoped.dbc", "vehicle_id": "v1"},
        }}, [item],
    )).stages[0].config
    assert scoped["dbc_path"] == "/scoped.dbc"
    assert scoped["vehicle_id"] == "v1"


class _EmptyStage:
    name = "local-validate"
    stage_version = "issue-702"

    def execute(self, records, config=None):
        return []


def test_zero_output_aborts_before_bundle_publication(tmp_path: Path) -> None:
    source = tmp_path / "source.jsonl"
    source.write_text('{"messages":[{"role":"user","content":"input"}]}\n')
    recipe = tmp_path / "recipe.json"
    content = b'{"version":"1","stages":[{"name":"local-validate"}]}'
    recipe.write_bytes(content)
    request = _request(tmp_path, recipe.as_uri(), {}, [DatasetInputRef(
        uri=source.as_uri(), digest=hashlib.sha256(source.read_bytes()).hexdigest(),
    )]).model_copy(update={"recipe_digest": hashlib.sha256(content).hexdigest()})
    store = LocalDatasetStore(tmp_path / "store")
    status = DatasetJobStatus(
        job_id="empty-job", status="running", submitted_at=datetime.now(UTC),
        request=request,
    )
    store.save_job(status)
    with pytest.raises(ValueError, match="zero records"):
        LocalDatasetMaterializer(store, {"local-validate": _EmptyStage()}).materialize(status)
    assert not any(store.artifacts_dir.iterdir())


def test_verifier_rejects_empty_record_bundle_metadata(tmp_path: Path) -> None:
    request = _request(tmp_path, "recipe://local/pass-through@1", {})
    store = LocalDatasetStore(tmp_path / "store")
    recipe = DatasetRecipe(version="1", stages=[{"name": "local-validate"}])
    artifact = write_bundle(
        store, [], request, recipe, "forged-empty", {}, [], evaluate_quality([]),
        DatasetProvenanceRecord(materializer="test", job_id="forged-empty"), None,
    )
    with pytest.raises(ValueError, match="no verified records"):
        verify_artifact(artifact, store.manifests_dir, store.artifacts_dir)


def test_verifier_rejects_whitespace_only_forged_artifact(tmp_path: Path) -> None:
    request = _request(tmp_path, "recipe://local/pass-through@1", {})
    store = LocalDatasetStore(tmp_path / "store")
    recipe = DatasetRecipe(version="1", stages=[{"name": "local-validate"}])
    artifact = write_bundle(
        store, [], request, recipe, "forged-whitespace", {}, [], evaluate_quality([]),
        DatasetProvenanceRecord(materializer="test", job_id="forged-whitespace"), None,
    )
    dataset_path = path_from_uri(artifact.dataset_uri)
    dataset_path.chmod(0o644)
    dataset_path.write_bytes(b"\n\t")
    digest = hashlib.sha256(dataset_path.read_bytes()).hexdigest()
    manifest_path = path_from_uri(artifact.manifest_uri)
    from factory.dataset.runtime.contracts import DatasetManifest
    manifest = DatasetManifest.model_validate_json(manifest_path.read_bytes()).model_copy(
        update={
            "dataset_digest": digest,
            "training_uri": None,
            "quality_results": evaluate_quality([{
                "messages": [
                    {"role": "user", "content": "input"},
                    {"role": "assistant", "content": "output"},
                ],
            }]),
        },
    )
    manifest_content = manifest.model_dump_json(exclude_none=True).encode()
    forged_manifest = store.manifests_dir / (
        f"manifest-{hashlib.sha256(manifest_content).hexdigest()}.json"
    )
    forged_manifest.write_bytes(manifest_content)
    forged = artifact.model_copy(update={
        "digest": digest, "manifest_uri": forged_manifest.as_uri(), "training_uri": None,
    })
    with pytest.raises(ValueError, match="no verified records"):
        verify_artifact(forged, store.manifests_dir, store.artifacts_dir)
