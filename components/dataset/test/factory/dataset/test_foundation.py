"""Contract tests for the local durable dataset foundation."""

from __future__ import annotations

import asyncio
from pathlib import Path
import hashlib
import json
import time

import pytest
from pydantic import ValidationError

from factory.dataset.interface import (
    dataset_get_artifact,
    dataset_get_job,
    dataset_resolve_artifact,
    dataset_submit_generation,
)
from factory.dataset.runtime.contracts import (
    DatasetExecutionPolicy,
    DatasetGenerationRequest,
    DatasetInputRef,
    DatasetSnapshotRef,
    DatasetToolSchemaSnapshotRef,
)


async def _completed_job(job_id: str, root: Path):
    for _ in range(750):  # ~15s budget: de-flake worker wait on loaded CI
        status = dataset_get_job(job_id, root)
        if status and status.status in {"completed", "failed"}:
            return status
        await asyncio.sleep(0.02)
    pytest.fail("dataset worker did not reach a terminal state")


def _snapshot_ref(root: Path, label: str, content: bytes) -> DatasetSnapshotRef:
    snapshot_dir = root / "snapshots"
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(content).hexdigest()
    path = snapshot_dir / f"{label}-{digest}.json"
    if path.exists():
        assert path.read_bytes() == content
    else:
        path.write_bytes(content)
        path.chmod(0o444)
    return DatasetSnapshotRef(uri=path.as_uri(), digest=digest)


def _tool_schema_snapshot_ref(
    root: Path,
    allowed_tools: list[str] | None = None,
) -> DatasetToolSchemaSnapshotRef:
    allowed_tools = allowed_tools or []
    content = json.dumps({"allowed_tools": allowed_tools}, sort_keys=True).encode()
    snapshot = _snapshot_ref(root, "tool-schema", content)
    return DatasetToolSchemaSnapshotRef(
        uri=snapshot.uri,
        digest=snapshot.digest,
        allowed_tools=allowed_tools,
    )


def _request(
    source: Path,
    root: Path,
    *,
    allowed_tools: list[str] | None = None,
    execution_policy: DatasetExecutionPolicy | None = None,
) -> DatasetGenerationRequest:
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    recipe_uri = "recipe://local/pass-through@1"
    return DatasetGenerationRequest(
        recipe_uri=recipe_uri,
        recipe_digest=hashlib.sha256(recipe_uri.encode()).hexdigest(),
        input_artifacts=[DatasetInputRef(uri=source.as_uri(), digest=digest)],
        requested_views=["sft"],
        idempotency_key="foundation-test",
        context_snapshot=_snapshot_ref(root, "context", b'{"source":"foundation-test"}'),
        tool_schema_snapshot=_tool_schema_snapshot_ref(root, allowed_tools=allowed_tools),
        execution_policy=execution_policy or DatasetExecutionPolicy(),
    )


def test_generation_request_requires_explicit_snapshots() -> None:
    recipe_uri = "recipe://local/pass-through@1"
    with pytest.raises(ValidationError):
        DatasetGenerationRequest(
            recipe_uri=recipe_uri,
            recipe_digest=hashlib.sha256(recipe_uri.encode()).hexdigest(),
        )


@pytest.mark.asyncio
async def test_submission_returns_immediately_and_reaches_completed(tmp_path: Path) -> None:
    source = tmp_path / "records.jsonl"
    source.write_text('{"messages":[{"role":"user","content":"one"}]}\n')

    started = time.monotonic()
    receipt = dataset_submit_generation(_request(source, tmp_path), tmp_path / "store")

    assert receipt.status == "queued"
    assert time.monotonic() - started < 0.5
    completed = await _completed_job(receipt.job_id, tmp_path / "store")
    assert completed.status == "completed"
    assert completed.started_at is not None
    assert completed.completed_at is not None


@pytest.mark.asyncio
async def test_duplicate_submission_reuses_existing_job_id(tmp_path: Path) -> None:
    source = tmp_path / "records.jsonl"
    source.write_text('{"messages":[{"role":"user","content":"one"}]}\n')
    root = tmp_path / "store"

    first = dataset_submit_generation(_request(source, tmp_path), root)
    second = dataset_submit_generation(_request(source, tmp_path), root)

    assert second.job_id == first.job_id
    assert second.submitted_at == first.submitted_at

    completed = await _completed_job(first.job_id, root)
    assert completed.status == "completed"
    assert len(list((root / "jobs").glob("*.json"))) == 1


@pytest.mark.asyncio
async def test_artifact_and_manifest_are_integrity_addressed(tmp_path: Path) -> None:
    source = tmp_path / "records.jsonl"
    source.write_text(
        '{"messages":[{"role":"user","content":"one"},{"role":"assistant","content":"one reply"}]}\n'
        '{"messages":[{"role":"user","content":"two"},{"role":"assistant","content":"two reply"}]}\n'
    )
    root = tmp_path / "store"
    request = _request(source, tmp_path)
    receipt = dataset_submit_generation(request, root)
    completed = await _completed_job(receipt.job_id, root)

    assert completed.status == "completed"
    artifact = dataset_get_artifact(receipt.job_id, root)
    assert artifact is not None
    artifact_path = Path(artifact.dataset_uri.removeprefix("file://"))
    manifest_path = Path(artifact.manifest_uri.removeprefix("file://"))
    assert hashlib.sha256(artifact_path.read_bytes()).hexdigest() == artifact.digest
    assert hashlib.sha256(manifest_path.read_bytes()).hexdigest() in manifest_path.name
    manifest = dataset_resolve_artifact(artifact.dataset_uri, root)
    assert manifest is not None
    assert manifest.dataset_uri == artifact.dataset_uri
    assert manifest.dataset_digest == artifact.digest
    assert manifest.manifest_uri == artifact.manifest_uri
    assert manifest.training_views == ["sft"]
    assert manifest.view_schema_versions == {"sft": "1.0"}
    assert manifest.input_artifacts[0].uri == source.as_uri()
    assert manifest.context_snapshot.uri == request.context_snapshot.uri
    assert manifest.context_snapshot.digest == request.context_snapshot.digest
    assert manifest.tool_schema_snapshot.uri == request.tool_schema_snapshot.uri
    assert manifest.tool_schema_snapshot.digest == request.tool_schema_snapshot.digest
    assert manifest.execution_policy.fail_closed is True
    assert manifest.execution_policy.allowed_fallbacks == []
    assert manifest.execution_policy.retry_from_checkpoint_only is True
    assert manifest.quality_results.passed is True
    assert manifest.quality_results.checks["schema"] == "passed"
    assert manifest.quality_results.checks["record_count"] == "passed: 2"
    assert manifest.provenance.materializer == "local-recipe"
    assert manifest.provenance.job_id == receipt.job_id
    assert manifest.stage_lineage
    assert manifest.stage_lineage[0].context_snapshot_digest == request.context_snapshot.digest
    assert manifest.stage_lineage[0].tool_schema_snapshot_digest == request.tool_schema_snapshot.digest
    assert artifact.training_uri is not None
    assert Path(artifact.training_uri.removeprefix("file://")).exists()


def test_unknown_jobs_have_no_status_or_artifact(tmp_path: Path) -> None:
    root = tmp_path / "store"
    assert dataset_get_job("missing", root) is None
    assert dataset_get_artifact("missing", root) is None


def test_artifact_resolution_rejects_forged_sidecar(tmp_path: Path) -> None:
    source = tmp_path / "records.jsonl"
    source.write_text('{"messages":[{"role":"user","content":"one"}]}\n')
    root = tmp_path / "store"
    receipt = dataset_submit_generation(_request(source, tmp_path), root)
    artifact = asyncio.run(_completed_job(receipt.job_id, root)).artifact
    assert artifact is not None
    reference_path = Path(artifact.dataset_uri.removeprefix("file://")).with_suffix(".ref.json")
    reference_path.chmod(0o644)
    reference_path.write_text(
        artifact.model_copy(update={"manifest_uri": (tmp_path / "forged.json").as_uri()}).model_dump_json()
    )

    with pytest.raises(ValueError, match="does not match|missing"):
        dataset_resolve_artifact(artifact.dataset_uri, root)


def test_artifact_getter_rejects_forged_digest(tmp_path: Path) -> None:
    source = tmp_path / "records.jsonl"
    source.write_text('{"messages":[{"role":"user","content":"one"}]}\n')
    root = tmp_path / "store"
    receipt = dataset_submit_generation(_request(source, tmp_path), root)
    artifact = asyncio.run(_completed_job(receipt.job_id, root)).artifact
    assert artifact is not None
    reference_path = Path(artifact.dataset_uri.removeprefix("file://")).with_suffix(".ref.json")
    reference_path.chmod(0o644)
    reference_path.write_text(artifact.model_copy(update={"digest": "0" * 64}).model_dump_json())

    with pytest.raises(ValueError, match="digest"):
        dataset_get_artifact(receipt.job_id, root)


def test_artifact_getter_rejects_sidecar_for_another_dataset(tmp_path: Path) -> None:
    source = tmp_path / "records.jsonl"
    source.write_text('{"messages":[{"role":"user","content":"one"}]}\n')
    root = tmp_path / "store"
    receipt = dataset_submit_generation(_request(source, tmp_path), root)
    artifact = asyncio.run(_completed_job(receipt.job_id, root)).artifact
    assert artifact is not None
    reference_path = Path(artifact.dataset_uri.removeprefix("file://")).with_suffix(".ref.json")
    reference_path.chmod(0o644)
    forged = artifact.model_copy(update={"dataset_uri": (tmp_path / "other.jsonl").as_uri()})
    reference_path.write_text(forged.model_dump_json())

    with pytest.raises(ValueError, match="does not belong"):
        dataset_get_artifact(receipt.job_id, root)


def test_artifact_resolution_rejects_external_dataset_pointer(tmp_path: Path) -> None:
    source = tmp_path / "records.jsonl"
    source.write_text('{"messages":[{"role":"user","content":"one"}]}\n')
    root = tmp_path / "store"
    receipt = dataset_submit_generation(_request(source, tmp_path), root)
    artifact = asyncio.run(_completed_job(receipt.job_id, root)).artifact
    assert artifact is not None
    external = tmp_path / "external.jsonl"
    external.write_bytes(Path(artifact.dataset_uri.removeprefix("file://")).read_bytes())
    external_reference = external.with_suffix(".ref.json")
    external_reference.write_text(artifact.model_copy(update={"dataset_uri": external.as_uri()}).model_dump_json())

    with pytest.raises(ValueError, match="outside"):
        dataset_resolve_artifact(external.as_uri(), root)


def test_artifact_getter_rejects_forged_view_metadata(tmp_path: Path) -> None:
    source = tmp_path / "records.jsonl"
    source.write_text('{"messages":[{"role":"user","content":"one"}]}\n')
    root = tmp_path / "store"
    receipt = dataset_submit_generation(_request(source, tmp_path), root)
    artifact = asyncio.run(_completed_job(receipt.job_id, root)).artifact
    assert artifact is not None
    reference_path = Path(artifact.dataset_uri.removeprefix("file://")).with_suffix(".ref.json")
    reference_path.chmod(0o644)
    reference_path.write_text(artifact.model_copy(update={"available_views": ["dpo"]}).model_dump_json())

    with pytest.raises(ValueError, match="does not match"):
        dataset_get_artifact(receipt.job_id, root)


def test_requested_view_empty_list_is_rejected(tmp_path: Path) -> None:
    recipe_uri = "recipe://local/pass-through@1"
    with pytest.raises(ValidationError):
        DatasetGenerationRequest(
            recipe_uri=recipe_uri,
            recipe_digest=hashlib.sha256(recipe_uri.encode()).hexdigest(),
            requested_views=[],
            context_snapshot=_snapshot_ref(tmp_path, "context", b'{"source":"empty-view-test"}'),
            tool_schema_snapshot=_tool_schema_snapshot_ref(tmp_path),
        )


def test_requested_view_duplicate_names_are_rejected(tmp_path: Path) -> None:
    recipe_uri = "recipe://local/pass-through@1"
    with pytest.raises(ValidationError):
        DatasetGenerationRequest(
            recipe_uri=recipe_uri,
            recipe_digest=hashlib.sha256(recipe_uri.encode()).hexdigest(),
            requested_views=["sft", "sft"],
            context_snapshot=_snapshot_ref(tmp_path, "context", b'{"source":"dup-view-test"}'),
            tool_schema_snapshot=_tool_schema_snapshot_ref(tmp_path),
        )


def test_relative_store_root_resolves_materialized_artifact(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / "records.jsonl"
    source.write_text('{"messages":[{"role":"user","content":"one"}]}\n')
    monkeypatch.chdir(tmp_path)
    root = Path("relative-store")
    receipt = dataset_submit_generation(_request(source, tmp_path), root)
    artifact = asyncio.run(_completed_job(receipt.job_id, root)).artifact
    assert artifact is not None
    assert dataset_get_artifact(receipt.job_id, root) == artifact