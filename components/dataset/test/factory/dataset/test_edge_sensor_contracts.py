"""Contracts and leakage checks for edge sensor-window datasets."""

from __future__ import annotations

from pathlib import Path

import pytest
from factory.dataset.mcp.contracts.lifecycle import SubmitGenerationInput
from factory.dataset.runtime.contracts import (
    DatasetGenerationRequest,
    DatasetRecipe,
    DatasetSnapshotRef,
    DatasetToolSchemaSnapshotRef,
)
from factory.dataset.runtime.edge_sensor_contracts import EdgeSensorWindowRecord
from factory.dataset.runtime.quality import evaluate_quality
from factory.dataset.runtime.validation import dispatch_validator
from pydantic import ValidationError

from .edge_sensor_fixtures import sensor_record as _record
from .edge_sensor_fixtures import stored_sensor_record as _stored_record


def test_edge_sensor_window_contract_accepts_versioned_record() -> None:
    record = _record("window-1", "session-1", "train")

    validated = list(dispatch_validator([record], record_schema="edge_sensor_window"))

    assert validated[0].record_id == "window-1"
    assert validated[0].input_ref.sha256 == record["input_ref"]["sha256"]


def test_edge_sensor_evidence_records_are_deeply_immutable() -> None:
    source = _record("window-1", "session-1", "train")
    validated = EdgeSensorWindowRecord.model_validate(source)
    source["input_ref"]["uri"] = "file:///changed/window.json"

    assert validated.input_ref.uri == "file:///windows/window-1.json"
    with pytest.raises(ValidationError):
        validated.record_id = "changed"
    with pytest.raises(ValidationError):
        validated.input_ref.uri = "file:///changed/window.json"
    with pytest.raises(ValidationError):
        validated.label_provenance.source = "changed"


def test_dataset_recipe_accepts_edge_sensor_schema() -> None:
    recipe = DatasetRecipe.model_validate({
        "version": "edge-v1",
        "stages": [{"name": "local-validate"}],
        "record_schema": "edge_sensor_window",
    })

    assert recipe.record_schema == "edge_sensor_window"


def test_allowed_local_roots_round_trip_through_request_and_public_boundary(
    tmp_path: Path,
) -> None:
    request = DatasetGenerationRequest(
        recipe_uri="file:///recipe.json", recipe_digest="0" * 64,
        context_snapshot=DatasetSnapshotRef(uri="file:///context.json", digest="1" * 64),
        tool_schema_snapshot=DatasetToolSchemaSnapshotRef(
            uri="file:///tools.json", digest="2" * 64,
        ),
        allowed_local_roots=(tmp_path,),
    )

    restored = DatasetGenerationRequest.model_validate_json(request.model_dump_json())
    public = SubmitGenerationInput.model_validate({
        "recipe_uri": "file:///recipe.json", "recipe_digest": "0" * 64,
        "context_snapshot_uri": "file:///context.json",
        "context_snapshot_digest": "1" * 64,
        "tool_schema_snapshot_uri": "file:///tools.json",
        "tool_schema_snapshot_digest": "2" * 64,
        "allowed_local_roots": [str(tmp_path)],
    })

    assert restored.allowed_local_roots == (tmp_path,)
    assert public.allowed_local_roots == [str(tmp_path)]


@pytest.mark.parametrize("roots", [["relative"], ["/tmp/a/../b"], ["/tmp/a", "/tmp/a"]])
def test_allowed_local_roots_reject_relative_traversal_and_duplicates(roots) -> None:
    with pytest.raises(ValidationError):
        DatasetGenerationRequest(
            recipe_uri="file:///recipe.json", recipe_digest="0" * 64,
            context_snapshot=DatasetSnapshotRef(uri="file:///context.json", digest="1" * 64),
            tool_schema_snapshot=DatasetToolSchemaSnapshotRef(
                uri="file:///tools.json", digest="2" * 64,
            ),
            allowed_local_roots=roots,
        )


@pytest.mark.parametrize(
    "change",
    [
        {"schema_version": "2.0"},
        {"unexpected": "field"},
        {"group_id": "  "},
        {"split": "holdout"},
        {"input_ref": {"uri": "file:///x", "sha256": "bad"}},
        {"input_ref": {"uri": "file:///x"}},
        {"label_start_ms": 2000},
    ],
)
def test_edge_sensor_window_rejects_invalid_contract_fields(change: dict) -> None:
    record = _record("window-1", "session-1", "train")
    record.update(change)

    with pytest.raises((ValidationError, ValueError)):
        list(dispatch_validator([record], record_schema="edge_sensor_window"))


def test_edge_sensor_quality_proves_group_split_isolation(tmp_path: Path) -> None:
    records = [
        _stored_record(tmp_path, "train-1", "session-a", "train"),
        _stored_record(tmp_path, "validation-1", "session-b", "validation"),
        _stored_record(tmp_path, "test-1", "session-c", "test"),
    ]

    result = evaluate_quality(
        records, record_schema="edge_sensor_window", allowed_local_roots=(tmp_path,),
    )

    assert result.passed is True
    assert result.checks["required_splits"] == "passed"
    assert result.checks["group_split_isolation"] == "passed"
    assert result.checks["input_digest_split_isolation"] == "passed"
    assert result.checks["payload_integrity"] == (
        "passed: referenced payload bytes match SHA-256"
    )
    assert result.checks["record_ids"] == "passed"


def test_edge_sensor_quality_fails_when_group_crosses_splits(tmp_path: Path) -> None:
    records = [
        _stored_record(tmp_path, "train-1", "same-session", "train"),
        _stored_record(tmp_path, "validation-1", "same-session", "validation"),
        _stored_record(tmp_path, "test-1", "session-c", "test"),
    ]

    result = evaluate_quality(
        records, record_schema="edge_sensor_window", allowed_local_roots=(tmp_path,),
    )

    assert result.passed is False
    assert "same-session" in result.checks["group_split_isolation"]


def test_edge_sensor_quality_fails_duplicate_ids_and_missing_split(tmp_path: Path) -> None:
    records = [
        _stored_record(tmp_path, "duplicate-1", "session-a", "train") | {
            "record_id": "duplicate",
        },
        _stored_record(tmp_path, "duplicate-2", "session-b", "train") | {
            "record_id": "duplicate",
        },
    ]

    result = evaluate_quality(
        records, record_schema="edge_sensor_window", allowed_local_roots=(tmp_path,),
    )

    assert result.passed is False
    assert "duplicate" in result.checks["record_ids"]
    assert "validation" in result.checks["required_splits"]
