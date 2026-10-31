"""Authorization and policy enforcement tests for dataset materialization."""

from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path

import pytest

from factory.dataset.runtime.contracts import (
    DatasetExecutionPolicy,
    DatasetFallbackRecord,
    DatasetGenerationRequest,
    DatasetInputRef,
    DatasetJobStatus,
    DatasetSnapshotRef,
    DatasetToolSchemaSnapshotRef,
)
from factory.dataset.runtime.local import LocalDatasetMaterializer, LocalDatasetStore


def _snapshot(root: Path, label: str, content: bytes) -> DatasetSnapshotRef:
    snapshot_dir = root / "snapshots"
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(content).hexdigest()
    path = snapshot_dir / f"{label}-{digest}.json"
    if not path.exists():
        path.write_bytes(content)
        path.chmod(0o444)
    return DatasetSnapshotRef(uri=path.as_uri(), digest=digest)


def _tool_snapshot(root: Path) -> DatasetToolSchemaSnapshotRef:
    content = json.dumps({"allowed_tools": []}, sort_keys=True).encode()
    snapshot = _snapshot(root, "tool-schema", content)
    return DatasetToolSchemaSnapshotRef(uri=snapshot.uri, digest=snapshot.digest, allowed_tools=[])


def _recipe_file(tmp_path: Path, stage_name: str = "local-validate") -> tuple[Path, str]:
    recipe = tmp_path / "recipe.json"
    content = json.dumps(
        {"version": "auth-test-v1", "stages": [{"name": stage_name, "config": {}}]},
        separators=(",", ":"),
    ).encode()
    recipe.write_bytes(content)
    return recipe, hashlib.sha256(content).hexdigest()


def _base_request(tmp_path: Path, **overrides) -> DatasetGenerationRequest:
    source = tmp_path / "records.jsonl"
    source.write_text('{"messages":[{"role":"user","content":"hello"}]}\n')
    recipe_path, recipe_digest = _recipe_file(tmp_path)
    defaults = dict(
        recipe_uri=recipe_path.as_uri(),
        recipe_digest=recipe_digest,
        input_artifacts=[
            DatasetInputRef(
                uri=source.as_uri(),
                digest=hashlib.sha256(source.read_bytes()).hexdigest(),
            )
        ],
        requested_views=["sft"],
        context_snapshot=_snapshot(tmp_path, "context", b'{"source":"auth-test"}'),
        tool_schema_snapshot=_tool_snapshot(tmp_path),
        execution_policy=DatasetExecutionPolicy(),
    )
    defaults.update(overrides)
    return DatasetGenerationRequest(**defaults)


def _running_job(request: DatasetGenerationRequest, job_id: str = "auth-job") -> DatasetJobStatus:
    return DatasetJobStatus(
        job_id=job_id,
        status="running",
        submitted_at=datetime.now(UTC),
        started_at=datetime.now(UTC),
        request=request,
    )


class _FallbackStage:
    """Stage that injects a fallback record into the checkpoint."""

    name = "local-validate"
    stage_version = "test-fallback-v1"

    def __init__(self, fallback: DatasetFallbackRecord) -> None:
        self.fallback_record = fallback
        self._calls = 0

    def execute(self, records, config=None):
        self._calls += 1
        return records


class _PassStage:
    name = "local-validate"
    stage_version = "test-pass-v1"

    def execute(self, records, config=None):
        return records


def test_unauthorized_fallback_rejects_materialization(tmp_path: Path) -> None:
    unauthorized = DatasetFallbackRecord(
        requested_backend="bedrock",
        actual_backend="bedrock",
        reason="degraded",
        degraded_quality=True,
        authorized=False,
    )
    stage = _FallbackStage(unauthorized)
    request = _base_request(tmp_path)
    store = LocalDatasetStore(tmp_path / "store")
    status = _running_job(request)
    store.save_job(status)

    mat = LocalDatasetMaterializer(store, {"local-validate": stage})
    with pytest.raises(ValueError, match="must be explicitly authorized"):
        mat.materialize(status)


def test_authorized_fallback_outside_policy_rejects(tmp_path: Path) -> None:
    authorized = DatasetFallbackRecord(
        requested_backend="bedrock",
        actual_backend="bedrock",
        reason="transient",
        degraded_quality=False,
        authorized=True,
    )
    stage = _FallbackStage(authorized)
    request = _base_request(
        tmp_path,
        execution_policy=DatasetExecutionPolicy(allowed_fallbacks=["vertex"]),
    )
    store = LocalDatasetStore(tmp_path / "store")
    status = _running_job(request)
    store.save_job(status)

    mat = LocalDatasetMaterializer(store, {"local-validate": stage})
    with pytest.raises(ValueError, match="not allowed by policy"):
        mat.materialize(status)


def test_authorized_fallback_within_policy_succeeds(tmp_path: Path) -> None:
    authorized = DatasetFallbackRecord(
        requested_backend="bedrock",
        actual_backend="bedrock",
        reason="transient",
        degraded_quality=False,
        authorized=True,
    )
    stage = _FallbackStage(authorized)
    request = _base_request(
        tmp_path,
        execution_policy=DatasetExecutionPolicy(allowed_fallbacks=["bedrock"]),
    )
    store = LocalDatasetStore(tmp_path / "store")
    status = _running_job(request)
    store.save_job(status)

    mat = LocalDatasetMaterializer(store, {"local-validate": stage})
    artifact = mat.materialize(status)
    assert artifact is not None


def test_fail_closed_false_rejects_materialization(tmp_path: Path) -> None:
    request = _base_request(
        tmp_path,
        execution_policy=DatasetExecutionPolicy(fail_closed=False),
    )
    store = LocalDatasetStore(tmp_path / "store")
    status = _running_job(request)
    store.save_job(status)

    mat = LocalDatasetMaterializer(store, {"local-validate": _PassStage()})
    with pytest.raises(ValueError, match="must be fail-closed"):
        mat.materialize(status)
