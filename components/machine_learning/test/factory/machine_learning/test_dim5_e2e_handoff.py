"""End-to-end validation: dataset artifact → ML handoff (python-factory-dim.5)."""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

import pytest

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
from factory.machine_learning.runtime.adapters.dataset_resolver import McpDatasetResolver
from factory.machine_learning.runtime.models import DatasetTrainingInput


PASS_THROUGH_URI = "recipe://local/pass-through@1"
PASS_THROUGH_DIGEST = hashlib.sha256(PASS_THROUGH_URI.encode()).hexdigest()


def _make_request(tmp_path: Path) -> DatasetGenerationRequest:
    """Build an immutable pass-through generation request backed by tmp snapshots."""
    snapshot_dir = tmp_path / "snapshots"
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    ctx_content = b'{"source":"dim5-e2e"}'
    ctx_digest = hashlib.sha256(ctx_content).hexdigest()
    ctx_path = snapshot_dir / f"context-{ctx_digest}.json"
    ctx_path.write_bytes(ctx_content)

    tool_content = json.dumps({"allowed_tools": []}, sort_keys=True).encode()
    tool_digest = hashlib.sha256(tool_content).hexdigest()
    tool_path = snapshot_dir / f"tool-schema-{tool_digest}.json"
    tool_path.write_bytes(tool_content)

    source_content = (
        b'{"messages":[{"role":"user","content":"input"},'
        b'{"role":"assistant","content":"output"}]}\n'
    )
    source_path = tmp_path / "records.jsonl"
    source_path.write_bytes(source_content)

    return DatasetGenerationRequest(
        recipe_uri=PASS_THROUGH_URI,
        recipe_digest=PASS_THROUGH_DIGEST,
        input_artifacts=[DatasetInputRef(
            uri=source_path.as_uri(), digest=hashlib.sha256(source_content).hexdigest(),
        )],
        context_snapshot=DatasetSnapshotRef(uri=ctx_path.as_uri(), digest=ctx_digest),
        tool_schema_snapshot=DatasetToolSchemaSnapshotRef(
            uri=tool_path.as_uri(), digest=tool_digest, allowed_tools=[],
        ),
        requested_views=["sft"],
        execution_policy=DatasetExecutionPolicy(),
    )


def _poll_until_terminal(job_id: str, storage_root: Path, max_iters: int = 200) -> dict:
    """Block until the dataset worker reaches ``completed`` or ``failed``."""
    for _ in range(max_iters):
        status = dataset_get_job(job_id, storage_root)
        if status and status.status in ("completed", "failed"):
            return status.model_dump(mode="json")
        time.sleep(0.02)
    raise TimeoutError(f"Job {job_id} did not reach terminal state")


def _real_invoker(storage_root: Path):
    """Mimic the MCP tool invoker by calling the real dataset interface directly."""

    def invoker(tool_name: str, **kwargs):
        if tool_name == "dataset_resolve_artifact":
            manifest = dataset_resolve_artifact(kwargs["dataset_uri"], storage_root)
            return {
                "schema_version": "v1", "ok": manifest is not None,
                "data": manifest.model_dump(mode="json") if manifest else None,
                "error": None if manifest else "not found", "idempotency_key": None,
            }
        raise ValueError(f"Unknown tool: {tool_name}")

    return invoker


def test_e2e_dataset_artifact_resolves_through_mcp_resolver(tmp_path: Path) -> None:
    """Full lifecycle: submit → poll → artifact → MCP resolve → ResolvedTrainingDataset."""
    storage_root = tmp_path / "store"
    receipt = dataset_submit_generation(_make_request(tmp_path), storage_root)
    final = _poll_until_terminal(receipt.job_id, storage_root)
    assert final["status"] == "completed", f"dataset job failed: {final.get('error')}"

    artifact = dataset_get_artifact(receipt.job_id, storage_root)
    assert artifact is not None
    assert artifact.available_views == ["sft"]
    assert artifact.training_uri is not None
    view_schema_version = artifact.view_schema_versions["sft"]

    training_input = DatasetTrainingInput(
        dataset_uri=artifact.dataset_uri,
        manifest_uri=artifact.manifest_uri,
        dataset_digest=artifact.digest,
        view_name="sft",
        view_schema_version=view_schema_version,
    )
    resolver = McpDatasetResolver(invoker=_real_invoker(storage_root))
    resolved = resolver.resolve(training_input)

    assert resolved.training_uri == artifact.training_uri
    assert resolved.dataset_uri == artifact.dataset_uri
    assert resolved.manifest_uri == artifact.manifest_uri
    assert resolved.dataset_digest == artifact.digest
    assert resolved.view_name == "sft"
    assert resolved.view_schema_version == view_schema_version


def test_e2e_resolver_rejects_mismatched_dataset_digest(tmp_path: Path) -> None:
    """Resolver raises ValueError when the caller's digest does not match the manifest."""
    storage_root = tmp_path / "store"
    receipt = dataset_submit_generation(_make_request(tmp_path), storage_root)
    final = _poll_until_terminal(receipt.job_id, storage_root)
    assert final["status"] == "completed", f"dataset job failed: {final.get('error')}"

    artifact = dataset_get_artifact(receipt.job_id, storage_root)
    assert artifact is not None

    wrong_digest = "f" * 64
    assert wrong_digest != artifact.digest

    training_input = DatasetTrainingInput(
        dataset_uri=artifact.dataset_uri,
        manifest_uri=artifact.manifest_uri,
        dataset_digest=wrong_digest,
        view_name="sft",
        view_schema_version=artifact.view_schema_versions["sft"],
    )
    resolver = McpDatasetResolver(invoker=_real_invoker(storage_root))

    with pytest.raises(ValueError, match="dataset_digest mismatch"):
        resolver.resolve(training_input)


def test_e2e_resolver_rejects_unavailable_view(tmp_path: Path) -> None:
    """Resolver raises ValueError when the requested view is not in the manifest."""
    storage_root = tmp_path / "store"
    receipt = dataset_submit_generation(_make_request(tmp_path), storage_root)
    final = _poll_until_terminal(receipt.job_id, storage_root)
    assert final["status"] == "completed", f"dataset job failed: {final.get('error')}"

    artifact = dataset_get_artifact(receipt.job_id, storage_root)
    assert artifact is not None
    assert "dpo" not in artifact.available_views

    training_input = DatasetTrainingInput(
        dataset_uri=artifact.dataset_uri,
        manifest_uri=artifact.manifest_uri,
        dataset_digest=artifact.digest,
        view_name="dpo",
        view_schema_version="1.0",
    )
    resolver = McpDatasetResolver(invoker=_real_invoker(storage_root))

    with pytest.raises(ValueError, match="dataset view is unavailable"):
        resolver.resolve(training_input)
