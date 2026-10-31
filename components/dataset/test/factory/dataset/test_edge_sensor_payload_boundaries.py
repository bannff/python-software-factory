"""Payload schema and leakage evidence for edge sensor records."""

from __future__ import annotations

from pathlib import Path

import pytest
from factory.dataset.runtime.quality import evaluate_quality
from factory.dataset.runtime.recipe import path_from_uri
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from .edge_sensor_fixtures import sensor_payload as _sensor_payload
from .edge_sensor_fixtures import sensor_record as _record
from .edge_sensor_fixtures import stored_sensor_record as _stored_record

from .test_edge_sensor_payload_quality import _record
from .test_edge_sensor_payload_quality import _stored_record

@given(second_timestamp=st.integers(min_value=0, max_value=1000))
@settings(
    max_examples=12,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
def test_edge_sensor_quality_rejects_unordered_samples(
    tmp_path: Path, second_timestamp: int,
) -> None:
    malformed = _sensor_payload(timestamps=[1000, second_timestamp])
    record = _stored_record(
        tmp_path, "unordered", "device-a", "train", payload=malformed,
    )

    result = evaluate_quality(
        [record], record_schema="edge_sensor_window", allowed_local_roots=(tmp_path,),
    )

    assert result.passed is False
    assert "unordered" in result.checks["payload_semantics"]

def test_edge_sensor_quality_rejects_non_finite_sample_values(tmp_path: Path) -> None:
    malformed = _sensor_payload(rows=[[0], [float("nan")]])
    record = _stored_record(
        tmp_path, "non-finite", "device-a", "train", payload=malformed,
    )

    result = evaluate_quality(
        [record], record_schema="edge_sensor_window", allowed_local_roots=(tmp_path,),
    )

    assert result.passed is False
    assert "non-finite" in result.checks["payload_semantics"]

def test_edge_sensor_quality_rejects_observation_cut_mismatch(tmp_path: Path) -> None:
    record = _stored_record(tmp_path, "cut", "device-a", "train")
    record["observed_through_ms"] = 1500

    result = evaluate_quality(
        [record], record_schema="edge_sensor_window", allowed_local_roots=(tmp_path,),
    )

    assert result.passed is False
    assert "cut" in result.checks["payload_semantics"]
