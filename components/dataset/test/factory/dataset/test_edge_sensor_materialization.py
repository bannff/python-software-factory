"""Publication behavior for edge sensor datasets."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from factory.dataset.runtime.artifact_utils import verify_artifact
from factory.dataset.runtime.contracts import (
    DatasetGenerationRequest,
    DatasetInputRef,
    DatasetJobStatus,
    DatasetSnapshotRef,
    DatasetToolSchemaSnapshotRef,
)
from factory.dataset.runtime.local import LocalDatasetMaterializer, LocalDatasetStore
from factory.dataset.runtime.recipe import path_from_uri

from .edge_sensor_fixtures import sensor_payload as _sensor_payload
from .edge_sensor_fixtures import stored_sensor_record as _stored_record


def _edge_materializer_fixture(
    tmp_path: Path, records: list[dict], job_id: str,
) -> tuple[LocalDatasetMaterializer, LocalDatasetStore, DatasetJobStatus]:
    source = tmp_path / "edge-records.jsonl"
    source_content = b"".join(
        (json.dumps(record, sort_keys=True) + "\n").encode() for record in records
    )
    source.write_bytes(source_content)
    recipe = tmp_path / "edge-recipe.json"
    recipe_content = json.dumps({
        "version": "edge-materializer-v1",
        "stages": [{"name": "local-validate"}],
        "record_schema": "edge_sensor_window",
    }, separators=(",", ":")).encode()
    recipe.write_bytes(recipe_content)

    def snapshot(name: str, content: bytes) -> DatasetSnapshotRef:
        path = tmp_path / name
        path.write_bytes(content)
        return DatasetSnapshotRef(
            uri=path.as_uri(), digest=hashlib.sha256(content).hexdigest(),
        )

    context = snapshot("context.json", b"{}")
    tool_ref = snapshot("tools.json", b'{"allowed_tools": []}')
    request = DatasetGenerationRequest(
        recipe_uri=recipe.as_uri(),
        recipe_digest=hashlib.sha256(recipe_content).hexdigest(),
        input_artifacts=[DatasetInputRef(
            uri=source.as_uri(), digest=hashlib.sha256(source_content).hexdigest(),
        )],
        allowed_local_roots=(tmp_path,),
        context_snapshot=context,
        tool_schema_snapshot=DatasetToolSchemaSnapshotRef(
            uri=tool_ref.uri, digest=tool_ref.digest, allowed_tools=[],
        ),
    )
    status = DatasetJobStatus(
        job_id=job_id,
        status="running",
        submitted_at=datetime.now(UTC),
        request=request,
    )
    store = LocalDatasetStore(tmp_path / "dataset-store")
    store.save_job(status)
    return LocalDatasetMaterializer(store), store, status


def test_edge_sensor_materializer_publishes_only_verified_split_records(
    tmp_path: Path,
) -> None:
    payload_dir = tmp_path / "payloads"
    payload_dir.mkdir()
    records = [
        _stored_record(payload_dir, "train-1", "session-a", "train"),
        _stored_record(payload_dir, "validation-1", "session-b", "validation"),
        _stored_record(payload_dir, "test-1", "session-c", "test"),
    ]
    materializer, store, status = _edge_materializer_fixture(
        tmp_path, records, "edge-materializer",
    )

    artifact = materializer.materialize(status)

    assert artifact.dataset_uri.endswith(".jsonl")
    manifest = store.resolve_manifest(artifact.dataset_uri)
    assert manifest is not None
    assert manifest.quality_results.checks["payload_integrity"].startswith("passed:")
    assert manifest.allowed_local_roots == (tmp_path,)


def test_edge_sensor_materializer_rechecks_payload_before_publication(
    tmp_path: Path, monkeypatch,
) -> None:
    payload_dir = tmp_path / "payloads"
    payload_dir.mkdir()
    records = [
        _stored_record(payload_dir, "train-1", "session-a", "train"),
        _stored_record(payload_dir, "validation-1", "session-b", "validation"),
        _stored_record(payload_dir, "test-1", "session-c", "test"),
    ]
    materializer, store, status = _edge_materializer_fixture(
        tmp_path, records, "edge-raced-payload",
    )
    original_write_bundle = __import__(
        "factory.dataset.runtime.materializer", fromlist=["write_bundle"],
    ).write_bundle

    def mutate_then_write(*args, **kwargs):
        path_from_uri(records[0]["input_ref"]["uri"]).write_bytes(b"mutated before publish")
        return original_write_bundle(*args, **kwargs)

    monkeypatch.setattr(
        "factory.dataset.runtime.materializer.write_bundle", mutate_then_write,
    )

    with pytest.raises(ValueError, match="quality changed before publication"):
        materializer.materialize(status)

    assert list(store.manifests_dir.iterdir()) == []
    assert list(store.artifacts_dir.iterdir()) == []


def test_edge_sensor_public_verification_rejects_source_tampering(
    tmp_path: Path,
) -> None:
    payload_dir = tmp_path / "payloads"
    payload_dir.mkdir()
    records = [
        _stored_record(payload_dir, "train-1", "session-a", "train"),
        _stored_record(payload_dir, "validation-1", "session-b", "validation"),
        _stored_record(payload_dir, "test-1", "session-c", "test"),
    ]
    materializer, store, status = _edge_materializer_fixture(
        tmp_path, records, "edge-post-publication-tamper",
    )
    artifact = materializer.materialize(status)
    store.save_job(status.model_copy(update={
        "status": "completed", "artifact": artifact,
    }))
    path_from_uri(records[0]["input_ref"]["uri"]).write_bytes(b"changed source payload")

    with pytest.raises(ValueError, match="payload quality failed verification"):
        store.get_artifact(status.job_id)
    with pytest.raises(ValueError, match="payload quality failed verification"):
        store.resolve_manifest(artifact.dataset_uri)


def test_edge_sensor_public_verification_rejects_training_view_tampering(
    tmp_path: Path,
) -> None:
    payload_dir = tmp_path / "payloads"
    payload_dir.mkdir()
    records = [
        _stored_record(payload_dir, "train-1", "session-a", "train"),
        _stored_record(payload_dir, "validation-1", "session-b", "validation"),
        _stored_record(payload_dir, "test-1", "session-c", "test"),
    ]
    materializer, store, status = _edge_materializer_fixture(
        tmp_path, records, "edge-training-view-tamper",
    )
    artifact = materializer.materialize(status)
    training_path = path_from_uri(artifact.training_uri)
    training_path.chmod(0o600)
    training_path.write_bytes(b"changed training view")

    with pytest.raises(ValueError, match="Training view does not match the dataset artifact"):
        store.resolve_manifest(artifact.dataset_uri)
