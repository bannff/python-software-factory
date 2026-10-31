"""Completed job reads must not expose unverified routing training artifacts."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from factory.dataset.interface import dataset_get_job
from factory.dataset.runtime.artifact_utils import verify_artifact
from factory.dataset.runtime.bundle_writer import write_bundle
from factory.dataset.runtime.contracts import (
    DatasetArtifactRef,
    DatasetGenerationRequest,
    DatasetInputRef,
    DatasetJobStatus,
    DatasetManifest,
    DatasetProvenanceRecord,
    DatasetRecipe,
)
from factory.dataset.runtime.local import LocalDatasetStore
from factory.dataset.runtime.quality import evaluate_quality

from .test_edge_routing_views import _request, _synthetic_forgery


def _completed_status(
    store: LocalDatasetStore, artifact: DatasetArtifactRef,
    request: DatasetGenerationRequest, job_id: str,
) -> DatasetJobStatus:
    status = DatasetJobStatus(
        job_id=job_id, status="completed", submitted_at=datetime.now(UTC),
        completed_at=datetime.now(UTC), request=request, artifact=artifact,
    )
    store.save_job(status)
    return status


def _forged_routing_job(tmp_path: Path) -> tuple[LocalDatasetStore, DatasetJobStatus, Path]:
    store, artifact, dataset_path = _synthetic_forgery(tmp_path)
    recipe_path = tmp_path / "routing-recipe.json"
    recipe_content = json.dumps({
        "version": "routing-test-v1", "stages": [{"name": "local-validate"}],
        "record_schema": "edge_routing_example",
    }).encode()
    recipe_path.write_bytes(recipe_content)
    request = _request(["test", "validation", "train"]).model_copy(update={
        "recipe_uri": recipe_path.as_uri(),
        "recipe_digest": hashlib.sha256(recipe_content).hexdigest(),
    })
    original_manifest = DatasetManifest.model_validate_json(
        Path(artifact.manifest_uri.removeprefix("file://")).read_bytes(),
    )
    manifest = original_manifest.model_copy(update={
        "recipe_uri": request.recipe_uri,
        "recipe_digest": request.recipe_digest,
    })
    content = manifest.model_dump_json(exclude_none=True).encode()
    manifest_path = store.manifests_dir / (
        f"manifest-{hashlib.sha256(content).hexdigest()}.json"
    )
    manifest_path.write_bytes(content)
    artifact = artifact.model_copy(update={"manifest_uri": manifest_path.as_uri()})
    dataset_path.with_suffix(".ref.json").write_text(artifact.model_dump_json())
    return store, _completed_status(store, artifact, request, "routing-job"), dataset_path


@pytest.mark.parametrize("failure", ["quality_failed", "tampered_bytes"])
@pytest.mark.parametrize("read_via_interface", [False, True])
def test_completed_routing_job_read_rejects_unverified_artifact(
    tmp_path: Path, failure: str, read_via_interface: bool,
) -> None:
    store, status, dataset_path = _forged_routing_job(tmp_path)
    assert status.artifact is not None and status.artifact.training_uri is not None
    if failure == "tampered_bytes":
        dataset_path.write_bytes(dataset_path.read_bytes() + b"tampered\n")
    expected_error = "digest" if failure == "tampered_bytes" else "trusted provenance"
    with pytest.raises(ValueError, match=expected_error):
        verify_artifact(
            status.artifact, store.manifests_dir, store.artifacts_dir,
            request=status.request,
        )

    with pytest.raises(ValueError):
        if read_via_interface:
            dataset_get_job(status.job_id, store.root)
        else:
            store.get_job(status.job_id)


@pytest.mark.parametrize("state", ["queued", "running", "failed"])
@pytest.mark.parametrize("read_via_interface", [False, True])
def test_other_job_states_cannot_expose_unverified_artifact(
    tmp_path: Path, state: str, read_via_interface: bool,
) -> None:
    store, status, _ = _forged_routing_job(tmp_path)
    store.save_job(status.model_copy(update={"status": state}))

    with pytest.raises(ValueError):
        if read_via_interface:
            dataset_get_job(status.job_id, store.root)
        else:
            store.get_job(status.job_id)


def test_completed_job_requires_artifact(tmp_path: Path) -> None:
    store, status, _ = _forged_routing_job(tmp_path)
    store.save_job(status.model_copy(update={"artifact": None}))

    with pytest.raises(ValueError, match="no artifact"):
        store.get_job(status.job_id)


def _valid_generic_job(tmp_path: Path) -> tuple[LocalDatasetStore, DatasetJobStatus]:
    store = LocalDatasetStore(tmp_path / "store")
    recipe_path = tmp_path / "generic-recipe.json"
    recipe_content = json.dumps({
        "version": "generic-v1", "stages": [{"name": "local-validate"}],
        "record_schema": "generic",
    }).encode()
    recipe_path.write_bytes(recipe_content)
    request = _request(["default"]).model_copy(update={
        "recipe_uri": recipe_path.as_uri(),
        "recipe_digest": hashlib.sha256(recipe_content).hexdigest(),
    })
    records = [{"message": "normal dataset"}]
    artifact = write_bundle(
        store, records, request,
        DatasetRecipe(version="generic-v1", stages=[{"name": "local-validate"}],
                      record_schema="generic"),
        "ordinary-job", {}, [], evaluate_quality(records),
        DatasetProvenanceRecord(materializer="test", job_id="ordinary-job"), None,
    )
    status = _completed_status(store, artifact, request, "ordinary-job")
    verify_artifact(artifact, store.manifests_dir, store.artifacts_dir, request=request)
    return store, status


def test_completed_non_routing_job_read_keeps_its_artifact(tmp_path: Path) -> None:
    store, status = _valid_generic_job(tmp_path)

    assert store.get_job(status.job_id) == status
    assert dataset_get_job(status.job_id, store.root) == status


def test_completed_job_cannot_borrow_another_jobs_artifact(tmp_path: Path) -> None:
    store, status = _valid_generic_job(tmp_path)
    borrowed = status.model_copy(update={"job_id": "other-job"})
    store.save_job(borrowed)

    with pytest.raises(ValueError, match="job"):
        store.get_job(borrowed.job_id)


def test_completed_job_binds_submitted_input_artifacts(tmp_path: Path) -> None:
    store, status = _valid_generic_job(tmp_path)
    changed_request = status.request.model_copy(update={
        "input_artifacts": [DatasetInputRef(uri="file:///different-input", digest="0" * 64)],
    })
    store.save_job(status.model_copy(update={"request": changed_request}))

    with pytest.raises(ValueError, match="submitted request"):
        store.get_job(status.job_id)


def test_job_read_binds_requested_id_to_file_content(tmp_path: Path) -> None:
    store, status = _valid_generic_job(tmp_path)
    alias = "alias-job"
    (store.jobs_dir / f"{alias}.json").write_bytes(
        (store.jobs_dir / f"{status.job_id}.json").read_bytes()
    )

    with pytest.raises(ValueError, match="identity"):
        store.get_job(alias)


def test_job_read_rejects_unsafe_identifier(tmp_path: Path) -> None:
    store = LocalDatasetStore(tmp_path / "store")

    with pytest.raises(ValueError, match="job ID"):
        store.get_job("../outside")
