"""Temporary-store publication gates for routing dataset contract fixtures."""
from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from factory.dataset.runtime.contracts import (
    DatasetGenerationRequest,
    DatasetInputRef,
    DatasetJobStatus,
    DatasetSnapshotRef,
    DatasetStageCheckpoint,
    DatasetToolSchemaSnapshotRef,
)
from factory.dataset.runtime.local import LocalDatasetMaterializer, LocalDatasetStore

from .test_edge_routing_quality import _three_records


def _materializer_fixture(
    root: Path, records: list[dict], job_id: str,
) -> tuple[LocalDatasetMaterializer, LocalDatasetStore, DatasetJobStatus]:
    source = root / "routing-records.jsonl"
    source_bytes = b"".join(
        (json.dumps(record, sort_keys=True) + "\n").encode() for record in records
    )
    source.write_bytes(source_bytes)
    recipe = root / "routing-recipe.json"
    recipe_bytes = json.dumps({
        "version": "edge-routing-contract-fixture-v1",
        "stages": [{"name": "local-validate"}],
        "record_schema": "edge_routing_example",
    }, separators=(",", ":")).encode()
    recipe.write_bytes(recipe_bytes)

    def snapshot(name: str, content: bytes) -> DatasetSnapshotRef:
        path = root / name
        path.write_bytes(content)
        return DatasetSnapshotRef(
            uri=path.as_uri(), digest=hashlib.sha256(content).hexdigest(),
        )

    context = snapshot("context.json", b"{}")
    tools = snapshot("tools.json", b'{"allowed_tools": []}')
    request = DatasetGenerationRequest(
        recipe_uri=recipe.as_uri(), recipe_digest=hashlib.sha256(recipe_bytes).hexdigest(),
        input_artifacts=[DatasetInputRef(
            uri=source.as_uri(), digest=hashlib.sha256(source_bytes).hexdigest(),
        )],
        context_snapshot=context,
        tool_schema_snapshot=DatasetToolSchemaSnapshotRef(
            uri=tools.uri, digest=tools.digest, allowed_tools=[],
        ),
        requested_views=["train", "validation", "test"],
    )
    status = DatasetJobStatus(
        job_id=job_id, status="running", submitted_at=datetime.now(UTC),
        request=request,
    )
    store = LocalDatasetStore(root / "dataset-store")
    store.save_job(status)
    return LocalDatasetMaterializer(store), store, status


def test_synthetic_reviewed_fixture_cannot_publish_without_trusted_run(
    tmp_path: Path,
) -> None:
    materializer, store, status = _materializer_fixture(
        tmp_path, _three_records(tmp_path), "routing-contract-only",
    )
    with pytest.raises(ValueError, match="Edge routing dataset failed quality validation"):
        materializer.materialize(status)
    assert list(store.manifests_dir.iterdir()) == []
    assert list(store.artifacts_dir.iterdir()) == []


@pytest.mark.parametrize("failure", [
    "zero_labels", "missing_split", "bad_ref", "duplicate_id",
])
def test_routing_publication_fails_closed_on_quality_failure(
    tmp_path: Path, failure: str,
) -> None:
    records = _three_records(tmp_path)
    if failure == "zero_labels":
        for record in records:
            record["executed_route"] = None
            record["outcome"] = None
    elif failure == "missing_split":
        records.pop()
    elif failure == "duplicate_id":
        records.append(json.loads(json.dumps(records[0])))
    else:
        records[0]["outcome"]["outcome_ref"]["sha256"] = "0" * 64
    materializer, store, status = _materializer_fixture(
        tmp_path, records, f"routing-{failure}",
    )
    with pytest.raises(ValueError, match="Edge routing dataset failed quality validation"):
        materializer.materialize(status)
    assert list(store.manifests_dir.iterdir()) == []
    assert list(store.artifacts_dir.iterdir()) == []


def test_routing_resume_rechecks_referenced_bytes(tmp_path: Path) -> None:
    records = _three_records(tmp_path)
    materializer, store, status = _materializer_fixture(
        tmp_path, records, "routing-replay-check",
    )
    with pytest.raises(ValueError, match="Edge routing dataset failed quality validation"):
        materializer.materialize(status)
    outcome_uri = records[0]["outcome"]["outcome_ref"]["uri"]
    Path(outcome_uri.removeprefix("file://")).write_bytes(b"tampered after checkpoint")
    with pytest.raises(ValueError, match="quality results do not match output"):
        materializer.materialize(status)


def test_content_addressed_unrelated_outcome_fails_semantic_gate(
    tmp_path: Path,
) -> None:
    records = _three_records(tmp_path)
    ref = records[0]["outcome"]["outcome_ref"]
    path = Path(ref["uri"].removeprefix("file://"))
    payload = json.loads(path.read_bytes())
    payload["run_id"] = "unrelated-run"
    content = json.dumps(payload, sort_keys=True).encode()
    path.write_bytes(content)
    ref["sha256"] = hashlib.sha256(content).hexdigest()
    materializer, store, status = _materializer_fixture(
        tmp_path, records, "routing-unrelated-outcome",
    )
    with pytest.raises(ValueError, match="Edge routing dataset failed quality validation"):
        materializer.materialize(status)
    checkpoint_path = next((store.root / "checkpoints" / status.job_id).glob(
        "stage-*.checkpoint.json",
    ))
    checkpoint = DatasetStageCheckpoint.model_validate_json(checkpoint_path.read_bytes())
    assert "train" in checkpoint.quality_results.checks["evidence_semantics"]
    assert checkpoint.quality_results.checks["evidence_integrity"].startswith("passed:")
    assert list(store.manifests_dir.iterdir()) == []
