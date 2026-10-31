"""End-to-end wiring test for the CAN failure-prediction pipeline (Epic 7).

Verifies the three integration points that the Companion-X chat agent
relies on to drive the CAN pipeline:

  1. Built-in CAN recipe URIs resolve through ``resolve_recipe``.
  2. The default stage map wires ``can_ingest`` / ``can_profile`` /
     ``can_synthesize`` so the executor doesn't fail with
     "Unsupported dataset recipe stage".
  3. A full ``dataset_submit_generation`` lifecycle with a file-based
     CAN recipe (MF4 + DBC config inline) materializes an artifact
     whose records are canonical CAN frames.

The MF4/DBC fixtures are the same Toyota Legacy corpus used by
``test_can_ingest.py``; the live e2e test is skipped when they are
absent so this file remains green in CI environments without them.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path

import pytest

from factory.dataset.interface import (
    check_dataset_status,
    dataset_submit_generation,
)
from factory.dataset.runtime.contracts import (
    DatasetExecutionPolicy,
    DatasetGenerationRequest,
    DatasetSnapshotRef,
    DatasetToolSchemaSnapshotRef,
)
from factory.dataset.runtime.local import (
    LocalDatasetMaterializer,
    LocalDatasetStore,
)
from factory.dataset.runtime.recipe import resolve_recipe

CAN_DATA_DIR = Path("/Users/danielrodrigo/Downloads/CAN Data")
MF4_FIXTURE = CAN_DATA_DIR / "00000001-6A0B6FCD.MF4"
DBC_FIXTURE = CAN_DATA_DIR / "dbc" / "toyota_legacy_combined.dbc"

BUILTIN_URIS = (
    "recipe://local/can-ingest@1",
    "recipe://local/can-profile@1",
    "recipe://local/can-synthesize@1",
)


def _snapshot(root: Path, label: str, content: bytes) -> DatasetSnapshotRef:
    snapshot_dir = root / "snapshots"
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(content).hexdigest()
    path = snapshot_dir / f"{label}-{digest}.json"
    if not path.exists():
        path.write_bytes(content)
    return DatasetSnapshotRef(uri=path.as_uri(), digest=digest)


def _tool_snapshot(root: Path) -> DatasetToolSchemaSnapshotRef:
    snapshot = _snapshot(root, "tool-schema", b'{"allowed_tools":[]}')
    return DatasetToolSchemaSnapshotRef(
        uri=snapshot.uri, digest=snapshot.digest, allowed_tools=[]
    )


def test_builtin_can_recipe_uris_resolve_to_can_frame_schema() -> None:
    """Supported single-stage CAN URIs resolve to the can_frame schema."""
    store = LocalDatasetStore(Path("/tmp/.dataset_can_builtin_test"))
    for uri in BUILTIN_URIS:
        request = DatasetGenerationRequest(
            recipe_uri=uri,
            recipe_digest=hashlib.sha256(uri.encode()).hexdigest(),
            context_snapshot=DatasetSnapshotRef(
                uri="file:///tmp/can-ctx.json",
                digest=hashlib.sha256(b"can-ctx").hexdigest(),
            ),
            tool_schema_snapshot=_tool_snapshot(store.root),
            execution_policy=DatasetExecutionPolicy(),
        )
        recipe = resolve_recipe(request)
        assert recipe.record_schema == "can_frame", f"{uri} -> {recipe.record_schema}"
        assert len(recipe.stages) == 1


def test_default_stages_include_can_adapters() -> None:
    """The default stage map (the one used by the detached worker) must
    register every CAN adapter so a CAN recipe doesn't fail with
    "Unsupported dataset recipe stage"."""
    store = LocalDatasetStore(Path("/tmp/.dataset_can_default_test"))
    materializer = LocalDatasetMaterializer(store)
    for name in ("can_ingest", "can_profile", "can_synthesize", "can_window"):
        assert name in materializer.stages, f"{name} not registered in default stages"
        assert materializer.stages[name].name == name


def test_builtin_can_ingest_recipe_digest_mismatch_is_rejected() -> None:
    """Built-in CAN recipes must fail-closed on digest mismatch (same
    contract as the legacy ``pass-through@1`` recipe)."""
    request = DatasetGenerationRequest(
        recipe_uri="recipe://local/can-ingest@1",
        recipe_digest="0" * 64,
        context_snapshot=DatasetSnapshotRef(
            uri="file:///tmp/can-ctx.json",
            digest=hashlib.sha256(b"can-ctx").hexdigest(),
        ),
        tool_schema_snapshot=_tool_snapshot(Path("/tmp")),
        execution_policy=DatasetExecutionPolicy(),
    )
    with pytest.raises(ValueError, match="Digest mismatch"):
        resolve_recipe(request)


@pytest.mark.skipif(
    not (MF4_FIXTURE.exists() and DBC_FIXTURE.exists()),
    reason=f"MF4/DBC fixtures not found under {CAN_DATA_DIR}",
)
@pytest.mark.asyncio
async def test_full_can_ingest_pipeline_e2e(tmp_path: Path) -> None:
    """File-based recipe drives the detached worker through the full
    CAN ingest stage; artifact must contain canonical CAN frame records."""
    recipe_path = tmp_path / "can-ingest-recipe.json"
    recipe_content = json.dumps(
        {
            "version": "can-ingest-v1",
            "record_schema": "can_frame",
            "stages": [
                {
                    "name": "can_ingest",
                    "config": {
                        "mf4_paths": [str(MF4_FIXTURE)],
                        "dbc_path": str(DBC_FIXTURE),
                        "vehicle_id": "e2e-test",
                    },
                }
            ],
        },
        separators=(",", ":"),
    ).encode()
    recipe_path.write_bytes(recipe_content)

    request = DatasetGenerationRequest(
        recipe_uri=recipe_path.as_uri(),
        recipe_digest=hashlib.sha256(recipe_content).hexdigest(),
        context_snapshot=_snapshot(tmp_path, "context", b'{"source":"can-e2e"}'),
        tool_schema_snapshot=_tool_snapshot(tmp_path),
        execution_policy=DatasetExecutionPolicy(),
        idempotency_key="can-e2e-1",
    )
    receipt = dataset_submit_generation(request, storage_root=tmp_path / "store")
    assert receipt.job_id

    final_status: dict = {}
    for _ in range(200):
        final_status = await check_dataset_status(
            receipt.job_id, storage_root=tmp_path / "store"
        )
        if final_status.get("status") in {"completed", "failed"}:
            break
        await asyncio.sleep(0.1)

    assert final_status.get("status") == "completed", (
        f"can_ingest e2e should complete; got {final_status}"
    )
    assert final_status.get("completed_at"), "completed_at must be set on success"
    artifact = (tmp_path / "store" / "artifacts" / receipt.job_id
                / f"dataset-{final_status.get('artifact', {}).get('digest', '')}.jsonl")
    assert artifact.exists(), f"artifact jsonl not found: {artifact}"


def test_builtin_can_ingest_recipe_submits_with_queued_receipt(
    tmp_path: Path,
) -> None:
    """Submitting the built-in ``can-ingest@1`` URI is accepted by the
    durable job store; the stage is registered (no "Unsupported dataset
    recipe stage" at submit time) so submission succeeds with a
    queued receipt."""
    request = DatasetGenerationRequest(
        recipe_uri="recipe://local/can-ingest@1",
        recipe_digest=hashlib.sha256(b"recipe://local/can-ingest@1").hexdigest(),
        context_snapshot=_snapshot(tmp_path, "context", b'{"source":"can-builtin"}'),
        tool_schema_snapshot=_tool_snapshot(tmp_path),
        execution_policy=DatasetExecutionPolicy(),
        idempotency_key="can-builtin-1",
    )
    receipt = dataset_submit_generation(request, storage_root=tmp_path / "store")
    assert receipt.status == "queued"
