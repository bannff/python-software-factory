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

from .test_edge_sensor_materialization import _edge_materializer_fixture

def test_edge_sensor_verification_rejects_manifest_request_root_mismatch(
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
        tmp_path, records, "edge-root-policy-mismatch",
    )
    artifact = materializer.materialize(status)
    mismatched_request = status.request.model_copy(update={
        "allowed_local_roots": (tmp_path / "different-root",),
    })

    with pytest.raises(ValueError, match="local-root policy"):
        verify_artifact(
            artifact, store.manifests_dir, store.artifacts_dir,
            request=mismatched_request, expected_job_id=status.job_id,
        )

@pytest.mark.parametrize("failure", ["missing_payload", "mismatched_payload", "split_leakage"])
def test_edge_sensor_materializer_blocks_invalid_integrity_before_publication(
    tmp_path: Path, failure: str,
) -> None:
    payload_dir = tmp_path / "payloads"
    payload_dir.mkdir()
    shared = _sensor_payload()
    records = [
        _stored_record(
            payload_dir, "train", "group-a", "train",
            payload=shared if failure == "split_leakage" else None,
        ),
        _stored_record(
            payload_dir, "validation", "group-b", "validation",
            payload=shared if failure == "split_leakage" else None,
        ),
        _stored_record(payload_dir, "test", "group-c", "test"),
    ]
    first_payload = path_from_uri(records[0]["input_ref"]["uri"])
    if failure == "missing_payload":
        first_payload.unlink()
    elif failure == "mismatched_payload":
        first_payload.write_bytes(b"changed payload")
    materializer, store, status = _edge_materializer_fixture(
        tmp_path, records, f"edge-invalid-{failure}",
    )

    with pytest.raises(ValueError, match="failed split leakage validation"):
        materializer.materialize(status)

    assert list(store.manifests_dir.iterdir()) == []
    assert list(store.artifacts_dir.iterdir()) == []
