"""Checkpoint and publication behavior for edge sensor datasets."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from factory.dataset.runtime.adapters.checkpoints import LocalStageCheckpointStore
from factory.dataset.runtime.checkpoint_integrity import (
    checked_output_path,
    validate_checkpoint_metadata,
)
from factory.dataset.runtime.contracts import (
    DatasetGenerationRequest,
    DatasetProvenanceRecord,
    DatasetRecipe,
    DatasetSnapshotRef,
    DatasetToolSchemaSnapshotRef,
)
from factory.dataset.runtime.quality import evaluate_quality
from factory.dataset.runtime.recipe import path_from_uri
from factory.dataset.runtime.stage_runner import run_stage_loop
from factory.dataset.runtime.validation import dispatch_validator

from .edge_sensor_fixtures import stored_sensor_record as _stored_record


def test_edge_sensor_checkpoint_round_trip_recomputes_matching_quality(tmp_path) -> None:
    records = [
        _stored_record(tmp_path, "train-1", "session-a", "train"),
        _stored_record(tmp_path, "validation-1", "session-b", "validation"),
        _stored_record(tmp_path, "test-1", "session-c", "test"),
    ]
    roots = (tmp_path,)
    quality = evaluate_quality(
        records, record_schema="edge_sensor_window", allowed_local_roots=roots,
    )
    store = LocalStageCheckpointStore(tmp_path)
    checkpoint = store.save(
        stage_name="sensor_windows",
        stage_index=0,
        input_digest="0" * 64,
        records=records,
        schema_version="1.0",
        adapter_version="test-v1",
        config={},
        context_snapshot_digest="1" * 64,
        tool_schema_snapshot_digest="2" * 64,
        provenance=DatasetProvenanceRecord(
            materializer="local-recipe", job_id="job-edge",
        ),
        quality_results=quality,
        record_schema="edge_sensor_window",
        allowed_local_roots=roots,
    )
    loaded_records = [
        json.loads(line)
        for line in checked_output_path(
            checkpoint, tmp_path, "edge_sensor_window",
        ).read_text().splitlines()
    ]

    validate_checkpoint_metadata(
        checkpoint,
        list(dispatch_validator(
            loaded_records, record_schema="edge_sensor_window",
        )),
        job_id="job-edge",
        require_digest=True,
        record_schema="edge_sensor_window",
        allowed_local_roots=roots,
    )


def test_edge_sensor_stage_checkpoint_resume_uses_edge_schema(tmp_path: Path) -> None:
    records = [
        _stored_record(tmp_path, "train-1", "session-a", "train"),
        _stored_record(tmp_path, "validation-1", "session-b", "validation"),
        _stored_record(tmp_path, "test-1", "session-c", "test"),
    ]
    recipe = DatasetRecipe.model_validate({
        "version": "edge-v1",
        "stages": [{"name": "passthrough"}],
        "record_schema": "edge_sensor_window",
    })
    request = DatasetGenerationRequest(
        recipe_uri="file:///recipe.json",
        recipe_digest="0" * 64,
        context_snapshot=DatasetSnapshotRef(uri="file:///context.json", digest="1" * 64),
        tool_schema_snapshot=DatasetToolSchemaSnapshotRef(
            uri="file:///tools.json", digest="2" * 64,
        ),
        allowed_local_roots=(tmp_path,),
    )

    class _Passthrough:
        stage_version = "test-v1"

        def execute(self, source, config=None):
            return source

    checkpoints = LocalStageCheckpointStore(tmp_path / "checkpoints")
    first = run_stage_loop(
        recipe, request, records, {"passthrough": _Passthrough()},
        checkpoints, {}, "edge-job",
    )
    resumed = run_stage_loop(
        recipe, request, records, {"passthrough": _Passthrough()},
        checkpoints, {0: first[-1][0]}, "edge-job",
    )

    assert [record.model_dump(mode="json") for record in resumed[0]] == first[0]
    assert resumed[-1][0].quality_results.checks["payload_integrity"].startswith("passed:")

    changed_roots_request = request.model_copy(update={
        "allowed_local_roots": (tmp_path / "other",),
    })
    with pytest.raises(ValueError, match="local-root policy"):
        run_stage_loop(
            recipe, changed_roots_request, records, {"passthrough": _Passthrough()},
            checkpoints, {0: first[-1][0]}, "edge-job",
        )

    changed_payload = path_from_uri(records[0]["input_ref"]["uri"])
    changed_payload.write_bytes(b"changed after checkpoint")
    with pytest.raises(ValueError, match="quality results do not match"):
        run_stage_loop(
            recipe, request, records, {"passthrough": _Passthrough()},
            checkpoints, {0: first[-1][0]}, "edge-job",
        )
