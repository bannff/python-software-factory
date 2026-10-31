"""End-to-end recipe fixture for `python-factory-2sq` (Minimal Ollama e2e).

This test exercises the full dataset MCP flow using the built-in
`recipe://local/pass-through@1` recipe. The pass-through recipe performs no
actual LLM calls — it exists to validate that the plumbing (submission,
durable job dispatch, materialization, artifact emission, manifest
resolution, idempotency) wires together correctly without requiring a heavy
backend like Ollama. A real Ollama-backed recipe can be layered on top of
the same plumbing once the LLM routing contract is satisfied.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
import hashlib
import json

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


PASS_THROUGH_URI = "recipe://local/pass-through@1"
PASS_THROUGH_DIGEST = hashlib.sha256(PASS_THROUGH_URI.encode()).hexdigest()


async def _wait_for_terminal(job_id: str, root: Path) -> str:
    """Poll the durable job state until the worker reaches a terminal status."""
    for _ in range(200):
        status = dataset_get_job(job_id, root)
        if status is not None and status.status in {"completed", "failed"}:
            return status.status
        await asyncio.sleep(0.02)
    pytest.fail(f"dataset worker did not reach a terminal state for job={job_id}")


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
    return DatasetToolSchemaSnapshotRef(
        uri=snapshot.uri, digest=snapshot.digest, allowed_tools=[]
    )


def _build_request(
    source: Path,
    root: Path,
    *,
    idempotency_key: str | None = None,
    requested_views: list[str] | None = None,
) -> DatasetGenerationRequest:
    return DatasetGenerationRequest(
        recipe_uri=PASS_THROUGH_URI,
        recipe_digest=PASS_THROUGH_DIGEST,
        input_artifacts=[
            DatasetInputRef(
                uri=source.as_uri(),
                digest=hashlib.sha256(source.read_bytes()).hexdigest(),
            )
        ],
        requested_views=requested_views or ["sft"],
        idempotency_key=idempotency_key,
        context_snapshot=_snapshot(root, "context", b'{"source":"ollama-2sq-e2e"}'),
        tool_schema_snapshot=_tool_snapshot(root),
        execution_policy=DatasetExecutionPolicy(),
    )


@pytest.mark.asyncio
async def test_ollama_e2e_pass_through_recipe_full_lifecycle(tmp_path: Path) -> None:
    """Submit, poll, materialize, resolve, and verify the manifest end-to-end."""
    source = tmp_path / "records.jsonl"
    source.write_text(
        '{"messages":[{"role":"user","content":"hello"},'
        '{"role":"assistant","content":"hi"}]}\n'
    )
    root = tmp_path / "store"
    request = _build_request(source, tmp_path, idempotency_key="ollama-2sq-lifecycle")

    receipt = dataset_submit_generation(request, root)
    assert receipt.status == "queued"
    assert receipt.job_id

    final = await _wait_for_terminal(receipt.job_id, root)
    assert final == "completed"

    artifact = dataset_get_artifact(receipt.job_id, root)
    assert artifact is not None
    assert artifact.dataset_uri.startswith("file://")
    assert artifact.manifest_uri.startswith("file://")
    assert artifact.available_views == ["sft"]
    assert artifact.training_uri is not None
    assert artifact.digest == hashlib.sha256(
        Path(artifact.dataset_uri.removeprefix("file://")).read_bytes()
    ).hexdigest()

    manifest = dataset_resolve_artifact(artifact.dataset_uri, root)
    assert manifest is not None
    assert manifest.recipe_uri == PASS_THROUGH_URI
    assert manifest.recipe_digest == PASS_THROUGH_DIGEST
    assert manifest.dataset_uri == artifact.dataset_uri
    assert manifest.dataset_digest == artifact.digest
    assert manifest.manifest_uri == artifact.manifest_uri
    assert manifest.training_views == ["sft"]
    assert manifest.training_uri == artifact.training_uri
    assert manifest.quality_results.passed is True
    assert manifest.quality_results.checks
    assert manifest.provenance.materializer == "local-recipe"
    assert manifest.provenance.job_id == receipt.job_id
    assert manifest.context_snapshot.digest == request.context_snapshot.digest
    assert manifest.tool_schema_snapshot.digest == request.tool_schema_snapshot.digest
    assert manifest.execution_policy.fail_closed is True
    assert manifest.stage_lineage, "expected at least one stage checkpoint in lineage"


@pytest.mark.asyncio
async def test_ollama_e2e_idempotent_submission_returns_same_job(tmp_path: Path) -> None:
    """Submitting the same idempotency_key returns the existing job_id."""
    source = tmp_path / "records.jsonl"
    source.write_text('{"messages":[{"role":"user","content":"once"}]}\n')
    root = tmp_path / "store"
    request = _build_request(source, tmp_path, idempotency_key="ollama-2sq-idem")

    first = dataset_submit_generation(request, root)
    second = dataset_submit_generation(request, root)

    assert first.status == "queued"
    assert second.status == "queued"
    assert second.job_id == first.job_id
    assert second.submitted_at == first.submitted_at

    final = await _wait_for_terminal(first.job_id, root)
    assert final == "completed"

    job_files = list((root / "jobs").glob("*.json"))
    assert len(job_files) == 1, "idempotent submit must not create a second job record"
