"""End-to-end QA test for the CAN failure-prediction pipeline.

This test runs the full CAN pipeline through the public MCP interface,
driving all 3 stages (ingest, profile, synthesize) and verifying output
quality. It exercises the same code path a companion-x agent would use.

Steps:
1. Ingest one MF4 file via can-ingest@1
2. Profile the ingested data via can-profile@1
3. Synthesize 2x synthetic data via can-synthesize@1
4. Verify output quality (record counts, failure labels, constraint bounds)
5. Save a sample to /tmp/can_synthetic_sample.jsonl
"""
from __future__ import annotations

import asyncio
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
from factory.dataset.runtime.local import LocalDatasetStore

# --- Fixtures ---------------------------------------------------------------

CAN_DATA_DIR = Path("/Users/danielrodrigo/Downloads/CAN Data")
MF4_FILES = sorted(CAN_DATA_DIR.glob("*.MF4"))
MF4_FIXTURE = CAN_DATA_DIR / "00000001-6A0B6FCD.MF4"
DBC_FIXTURE = CAN_DATA_DIR / "dbc" / "toyota_legacy_combined.dbc"
SAMPLE_OUTPUT = Path("/tmp/can_synthetic_sample.jsonl")


def _available() -> bool:
    return MF4_FIXTURE.exists() and DBC_FIXTURE.exists()


def _storage_root(tmp_path: Path) -> Path:
    return tmp_path / "qa_store"


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


def _context_snapshot(root: Path, config: dict) -> DatasetSnapshotRef:
    content = json.dumps(config, sort_keys=True).encode()
    return _snapshot(root, "context", content)


def _poll_job_sync(
    job_id: str, storage_root: Path, max_wait: float = 120.0, interval: float = 0.5
) -> dict:
    """Poll dataset_get_job until terminal state or timeout."""
    start = time.monotonic()
    while True:
        status = dataset_get_job(job_id, storage_root=storage_root)
        if status is None:
            raise RuntimeError(f"Job {job_id} not found")
        result = status.model_dump(mode="json")
        if result.get("status") in {"completed", "failed"}:
            return result
        if time.monotonic() - start > max_wait:
            raise TimeoutError(f"Job {job_id} did not complete in {max_wait}s")
        time.sleep(interval)


# --- Step 1: Ingest ---------------------------------------------------------


@pytest.mark.skipif(not _available(), reason="MF4/DBC fixtures not found")
def test_can_ingest_produces_canonical_records(tmp_path: Path) -> None:
    """Submit can-ingest@1 and verify we get canonical CAN frame records."""
    storage = _storage_root(tmp_path)
    config = {
        "dbc_path": str(DBC_FIXTURE),
        "vehicle_id": "qa-e2e",
    }
    recipe_uri = "recipe://local/can-ingest@1"
    recipe_digest = hashlib.sha256(recipe_uri.encode()).hexdigest()
    input_digest = hashlib.sha256(MF4_FIXTURE.read_bytes()).hexdigest()

    request = DatasetGenerationRequest(
        recipe_uri=recipe_uri,
        recipe_digest=recipe_digest,
        input_artifacts=[DatasetInputRef(uri=MF4_FIXTURE.as_uri(), digest=input_digest)],
        context_snapshot=_context_snapshot(tmp_path, config),
        tool_schema_snapshot=_tool_snapshot(tmp_path),
        execution_policy=DatasetExecutionPolicy(),
        idempotency_key=f"can-qa-ingest-{MF4_FIXTURE.stem}",
    )
    receipt = dataset_submit_generation(request, storage_root=storage)
    assert receipt.status == "queued"
    print(f"\n[INGEST] Job {receipt.job_id} submitted")

    final = _poll_job_sync(receipt.job_id, storage)
    assert final["status"] == "completed", f"Ingest failed: {final.get('error')}"
    print(f"[INGEST] Completed at {final['completed_at']}")

    artifact = dataset_get_artifact(receipt.job_id, storage_root=storage)
    assert artifact is not None
    print(f"[INGEST] Artifact: {artifact.dataset_uri}")

    manifest = dataset_resolve_artifact(artifact.dataset_uri, storage_root=storage)
    assert manifest is not None
    assert manifest.quality_results.checks
    print(f"[INGEST] Quality checks: {manifest.quality_results.checks}")

    # Read the artifact JSONL to count records
    artifact_path = Path(artifact.dataset_uri.replace("file://", ""))
    records = []
    for line in artifact_path.read_text().splitlines():
        if line.strip():
            records.append(json.loads(line))

    print(f"[INGEST] Total records: {len(records)}")
    assert len(records) > 0, "Ingest produced zero records"

    # Verify canonical fields
    required_fields = {
        "timestamp_ns", "vehicle_id", "trip_id", "bus_name", "arbitration_id",
        "is_extended", "is_fd", "dlc", "data_bytes", "frame_type", "error_state",
        "source_ecu", "capture_source", "decoded_signals", "dbc_message_name",
    }
    for r in records:
        missing = required_fields - set(r.keys())
        assert not missing, f"Record missing fields: {missing}"

    decoded = [r for r in records if r.get("decoded_signals")]
    print(f"[INGEST] Decoded frames: {len(decoded)}/{len(records)}")
    assert len(decoded) > 0, "No frames decoded from DBC"

    # Save intermediate for next stage
    intermediate = tmp_path / "ingested.jsonl"
    with open(intermediate, "w") as f:
        for r in records:
            f.write(json.dumps(r, sort_keys=True) + "\n")
    print(f"[INGEST] Saved to {intermediate}")


# --- Full pipeline E2E -----------------------------------------------------


@pytest.mark.skipif(not _available(), reason="MF4/DBC fixtures not found")
def test_can_pipeline_e2e(tmp_path: Path) -> None:
    """Run the full 3-stage CAN pipeline end-to-end and validate output."""
    storage = _storage_root(tmp_path)

    # --- Stage 1: Ingest ---
    config = {
        "mf4_paths": [str(MF4_FIXTURE)],
        "dbc_path": str(DBC_FIXTURE),
        "vehicle_id": "qa-e2e",
    }
    recipe_uri = "recipe://local/can-ingest@1"
    recipe_digest = hashlib.sha256(recipe_uri.encode()).hexdigest()

    request = DatasetGenerationRequest(
        recipe_uri=recipe_uri,
        recipe_digest=recipe_digest,
        context_snapshot=_context_snapshot(tmp_path, config),
        tool_schema_snapshot=_tool_snapshot(tmp_path),
        execution_policy=DatasetExecutionPolicy(),
        idempotency_key=f"can-qa-pipeline-{MF4_FIXTURE.stem}",
    )
    receipt = dataset_submit_generation(request, storage_root=storage)
    print(f"\n[STAGE 1] Ingest job: {receipt.job_id}")
    final = _poll_job_sync(receipt.job_id, storage)
    assert final["status"] == "completed", f"Stage 1 failed: {final.get('error')}"

    artifact = dataset_get_artifact(receipt.job_id, storage_root=storage)
    assert artifact is not None
    artifact_path = Path(artifact.dataset_uri.replace("file://", ""))

    ingested = []
    for line in artifact_path.read_text().splitlines():
        if line.strip():
            ingested.append(json.loads(line))
    print(f"[STAGE 1] Ingested {len(ingested)} records")
    assert len(ingested) > 0

    # --- Stage 2: Profile ---
    config2 = {"window_ms": 10, "correlation_threshold": 0.7}
    recipe_uri2 = "recipe://local/can-profile@1"
    recipe_digest2 = hashlib.sha256(recipe_uri2.encode()).hexdigest()

    # Create input artifact from ingested data
    input_path = tmp_path / "ingested_for_profile.jsonl"
    with open(input_path, "w") as f:
        for r in ingested:
            f.write(json.dumps(r, sort_keys=True) + "\n")
    input_digest = hashlib.sha256(input_path.read_bytes()).hexdigest()

    request2 = DatasetGenerationRequest(
        recipe_uri=recipe_uri2,
        recipe_digest=recipe_digest2,
        input_artifacts=[DatasetInputRef(uri=input_path.as_uri(), digest=input_digest)],
        context_snapshot=_context_snapshot(tmp_path, config2),
        tool_schema_snapshot=_tool_snapshot(tmp_path),
        execution_policy=DatasetExecutionPolicy(),
        idempotency_key=f"can-qa-profile-{MF4_FIXTURE.stem}",
    )
    receipt2 = dataset_submit_generation(request2, storage_root=storage)
    print(f"\n[STAGE 2] Profile job: {receipt2.job_id}")
    final2 = _poll_job_sync(receipt2.job_id, storage)
    assert final2["status"] == "completed", f"Stage 2 failed: {final2.get('error')}"

    artifact2 = dataset_get_artifact(receipt2.job_id, storage_root=storage)
    assert artifact2 is not None
    artifact2_path = Path(artifact2.dataset_uri.replace("file://", ""))

    profile_records = []
    for line in artifact2_path.read_text().splitlines():
        if line.strip():
            profile_records.append(json.loads(line))

    # Profile stage yields a single constraint schema record
    assert len(profile_records) == 1, f"Expected 1 schema record, got {len(profile_records)}"
    schema = profile_records[0]
    print(f"[STAGE 2] Schema version: {schema['version']}")
    print(f"[STAGE 2] CAN IDs: {schema['summary']['total_can_ids']}")
    print(f"[STAGE 2] Total signals: {schema['summary']['total_signals']}")
    print(f"[STAGE 2] Total frames: {schema['summary']['total_frames']}")
    print(f"[STAGE 2] Time span: {schema['summary']['time_span_seconds']}s")
    assert schema["summary"]["total_can_ids"] > 0
    assert schema["summary"]["total_signals"] > 0

    # --- Stage 3: Synthesize ---
    config3 = {
        "multiplier": 2,
        "failure_rate": 0.1,
        "seed": 42,
        "constraint_schema": schema,
    }
    recipe_uri3 = "recipe://local/can-synthesize@1"
    recipe_digest3 = hashlib.sha256(recipe_uri3.encode()).hexdigest()

    request3 = DatasetGenerationRequest(
        recipe_uri=recipe_uri3,
        recipe_digest=recipe_digest3,
        input_artifacts=[DatasetInputRef(uri=input_path.as_uri(), digest=input_digest)],
        context_snapshot=_context_snapshot(tmp_path, config3),
        tool_schema_snapshot=_tool_snapshot(tmp_path),
        execution_policy=DatasetExecutionPolicy(),
        idempotency_key=f"can-qa-synth-{MF4_FIXTURE.stem}",
    )
    receipt3 = dataset_submit_generation(request3, storage_root=storage)
    print(f"\n[STAGE 3] Synthesize job: {receipt3.job_id}")
    final3 = _poll_job_sync(receipt3.job_id, storage)
    assert final3["status"] == "completed", f"Stage 3 failed: {final3.get('error')}"

    artifact3 = dataset_get_artifact(receipt3.job_id, storage_root=storage)
    assert artifact3 is not None
    artifact3_path = Path(artifact3.dataset_uri.replace("file://", ""))

    synthetic = []
    for line in artifact3_path.read_text().splitlines():
        if line.strip():
            synthetic.append(json.loads(line))
    print(f"\n[STAGE 3] Synthetic records: {len(synthetic)}")
    assert len(synthetic) > 0

    # --- Step 4: Verify output quality ---
    print("\n=== QUALITY VERIFICATION ===")
    print(f"Total ingested records: {len(ingested)}")
    print(f"Total synthetic records: {len(synthetic)}")

    # Count failure labels
    failures = [r for r in synthetic if r.get("is_failure") == 1]
    failure_rate_actual = len(failures) / len(synthetic) if synthetic else 0
    print(f"Failure records: {len(failures)} ({failure_rate_actual:.1%})")
    assert len(failures) > 0, "No failure labels injected"
    assert failure_rate_actual <= 0.5, f"Failure rate too high: {failure_rate_actual}"

    # Check failure modes
    failure_modes = {r.get("failure_mode") for r in failures}
    allowed_modes = {"signal_drift", "drop_to_zero", "out_of_sequence"}
    print(f"Failure modes used: {failure_modes}")
    assert failure_modes.issubset(allowed_modes), f"Unknown failure modes: {failure_modes - allowed_modes}"

    # Verify constraint bounds (only for non-failure records)
    non_failures = [r for r in synthetic if r.get("is_failure") == 0]
    violations = 0
    for r in non_failures:
        signals_meta = (schema["can_ids"].get(r["arbitration_id"]) or {}).get("signals") or {}
        for name, value in (r.get("decoded_signals") or {}).items():
            meta = signals_meta.get(name) or {}
            lo, hi = meta.get("min"), meta.get("max")
            if lo is not None and value < lo - 1e-6:
                violations += 1
            if hi is not None and value > hi + 1e-6:
                violations += 1
    print(f"Constraint violations in healthy records: {violations}")
    assert violations == 0, f"Found {violations} constraint violations"

    # Check capture_source
    synth_sources = {r.get("capture_source") for r in synthetic}
    print(f"Capture sources: {synth_sources}")
    assert synth_sources == {"synthetic"}, "All synthetic records must have capture_source=synthetic"

    # Check all synthetic records have decoded_signals
    no_signals = [r for r in synthetic if not r.get("decoded_signals")]
    print(f"Records without decoded signals: {len(no_signals)}")
    assert len(no_signals) == 0, "Synthetic records should always have decoded_signals"

    # Check correlations look reasonable (spot check)
    can_ids_with_correlations = [
        can_id for can_id, entry in schema["can_ids"].items()
        if entry.get("correlations")
    ]
    print(f"CAN IDs with correlations: {len(can_ids_with_correlations)}")
    if can_ids_with_correlations:
        sample_id = can_ids_with_correlations[0]
        sample_corrs = schema["can_ids"][sample_id]["correlations"]
        print(f"  Sample correlations for {sample_id}: {sample_corrs[:3]}")
        for a, b, r in sample_corrs:
            assert -1.0 <= r <= 1.0, f"Invalid correlation: {r}"

    # --- Step 5: Save sample ---
    sample_size = min(100, len(synthetic))
    sample = synthetic[:sample_size]
    with open(SAMPLE_OUTPUT, "w") as f:
        for r in sample:
            f.write(json.dumps(r, sort_keys=True) + "\n")
    print(f"\n=== SAMPLE SAVED ===")
    print(f"Sample ({sample_size} records) written to {SAMPLE_OUTPUT}")

    # --- Summary ---
    print("\n=== PIPELINE E2E SUMMARY ===")
    print(f"MF4 file: {MF4_FIXTURE.name}")
    print(f"DBC file: {DBC_FIXTURE.name}")
    print(f"Ingested records: {len(ingested)}")
    print(f"  Decoded: {len([r for r in ingested if r.get('decoded_signals')])}")
    print(f"  CAN IDs in schema: {schema['summary']['total_can_ids']}")
    print(f"  Signals profiled: {schema['summary']['total_signals']}")
    print(f"Synthetic records: {len(synthetic)}")
    print(f"  Multiplier: 2x")
    print(f"  Failure rate target: 10%")
    print(f"  Failure rate actual: {failure_rate_actual:.1%}")
    print(f"  Failure modes: {failure_modes}")
    print(f"  Constraint violations: {violations}")
    print(f"Pipeline status: ALL STAGES PASSED")
