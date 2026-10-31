"""Typed context artifact routing and materialization regressions."""
from __future__ import annotations

import asyncio
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from factory.dataset.mcp.operational import register
from factory.dataset.runtime.contracts import (
    DatasetGenerationRequest,
    DatasetInputRef,
    DatasetJobStatus,
    DatasetSnapshotRef,
    DatasetToolSchemaSnapshotRef,
)
from factory.dataset.runtime.local import (
    LocalDatasetMaterializer,
    LocalDatasetStore,
    _request_digest,
)
from factory.dataset.runtime.recipe import path_from_uri, resolve_recipe
from factory.mcp_utils.runtime.tool_catalog import ToolCatalog

from .test_context_recipe_routing import _input, _request

def test_heatmap_materialization_and_checkpoint_are_json_safe(tmp_path: Path):
    augmented = tmp_path / "augmented.jsonl"
    records = [
        {"timestamp_ns": i, "arbitration_id": "0x100",
         "decoded_signals": {"speed": i + 1}, "context": {"temp_c": float(i)},
         "failure_mode": "signal_drift" if i >= 2 else None}
        for i in range(4)
    ]
    augmented.write_text("".join(json.dumps(row) + "\n" for row in records))
    request = _request(
        tmp_path, "recipe://local/context-correlate@1",
        [_input(augmented, "context_augmented_can")],
        {"stage_overrides": {"context_correlate": {
            "context_features": ["temp_c"], "failure_modes": ["signal_drift"],
            "min_correlation": 0.0,
        }}},
    )
    store = LocalDatasetStore(tmp_path / "store")
    status = DatasetJobStatus(
        job_id="context-roundtrip", status="running", submitted_at=datetime.now(UTC),
        started_at=datetime.now(UTC), request=request,
    )
    store.save_job(status)
    artifact = LocalDatasetMaterializer(store).materialize(status)
    materialized = [json.loads(line) for line in path_from_uri(artifact.dataset_uri).read_text().splitlines()]
    json.dumps(materialized)
    assert materialized[-1]["record_type"] == "context_correlation_heatmap"
    assert isinstance(materialized[-1]["heatmap"], list)
    checkpoint = next((store.root / "checkpoints" / status.job_id).glob("*.checkpoint.json"))
    checkpoint_data = json.loads(checkpoint.read_text())
    checkpoint_rows = path_from_uri(checkpoint_data["output_uri"]).read_text().splitlines()
    assert [json.loads(line) for line in checkpoint_rows] == materialized
