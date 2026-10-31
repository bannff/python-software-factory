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


def test_edge_sensor_quality_rejects_unverified_payload_reference(tmp_path: Path) -> None:
    record = _record("missing", "session-a", "train")

    result = evaluate_quality(
        [record], record_schema="edge_sensor_window", allowed_local_roots=(tmp_path,),
    )

    assert result.passed is False
    assert "missing" in result.checks["payload_integrity"]


@pytest.mark.parametrize("link_kind", ["leaf", "parent"])
def test_edge_sensor_quality_rejects_symlink_payload_references(
    tmp_path: Path, link_kind: str,
) -> None:
    payload_dir = tmp_path / "payloads"
    payload_dir.mkdir()
    records = [
        _stored_record(payload_dir, "train", "group-a", "train"),
        _stored_record(payload_dir, "validation", "group-b", "validation"),
        _stored_record(payload_dir, "test", "group-c", "test"),
    ]
    target = path_from_uri(records[0]["input_ref"]["uri"])
    if link_kind == "leaf":
        alias = tmp_path / "window-link"
        alias.symlink_to(target)
    else:
        alias_dir = tmp_path / "payload-dir-link"
        alias_dir.symlink_to(payload_dir, target_is_directory=True)
        alias = alias_dir / target.name
    records[0]["input_ref"]["uri"] = alias.as_uri()

    result = evaluate_quality(
        records, record_schema="edge_sensor_window", allowed_local_roots=(tmp_path,),
    )

    assert result.passed is False
    assert "train" in result.checks["payload_integrity"]


def test_edge_sensor_quality_rejects_parent_traversal_reference(
    tmp_path: Path,
) -> None:
    record = _stored_record(tmp_path, "traversal", "device-a", "train")
    payload_path = Path(record["input_ref"]["uri"].removeprefix("file://"))
    record["input_ref"]["uri"] = (
        tmp_path / "nested" / ".." / payload_path.name
    ).as_uri()

    result = evaluate_quality(
        [record], record_schema="edge_sensor_window", allowed_local_roots=(tmp_path,),
    )

    assert result.passed is False
    assert "traversal" in result.checks["payload_integrity"]


def test_edge_sensor_quality_fails_closed_without_allowed_roots(tmp_path: Path) -> None:
    record = _stored_record(tmp_path, "unscoped", "device-a", "train")

    result = evaluate_quality([record], record_schema="edge_sensor_window")

    assert result.passed is False
    assert "unscoped" in result.checks["payload_integrity"]


def test_edge_sensor_quality_does_not_read_payload_outside_allowed_roots(
    tmp_path: Path,
) -> None:
    payload_root = tmp_path / "payloads"
    payload_root.mkdir()
    record = _stored_record(payload_root, "outside", "device-a", "train")

    result = evaluate_quality(
        [record], record_schema="edge_sensor_window",
        allowed_local_roots=(tmp_path / "approved",),
    )

    assert result.passed is False
    assert "outside" in result.checks["payload_integrity"]


def test_edge_sensor_quality_rejects_oversized_referenced_payload(
    tmp_path: Path,
) -> None:
    oversized = tmp_path / "oversized.window"
    content = b" " * (16 * 1024 * 1024 + 1)
    oversized.write_bytes(content)
    record = _record(
        "oversized", "device-a", "train", uri=oversized.as_uri(),
        payload=content,
    )

    result = evaluate_quality(
        [record], record_schema="edge_sensor_window", allowed_local_roots=(tmp_path,),
    )

    assert result.passed is False
    assert "oversized" in result.checks["payload_integrity"]


def test_edge_sensor_quality_rejects_same_input_digest_across_splits(
    tmp_path: Path,
) -> None:
    duplicate_bytes = _sensor_payload()
    records = [
        _stored_record(tmp_path, "train", "device-a", "train", payload=duplicate_bytes),
        _stored_record(
            tmp_path, "validation", "device-b", "validation", payload=duplicate_bytes,
        ),
        _stored_record(tmp_path, "test", "device-c", "test"),
    ]

    result = evaluate_quality(
        records, record_schema="edge_sensor_window", allowed_local_roots=(tmp_path,),
    )

    assert result.passed is False
    assert "input digests cross splits" in result.checks["input_digest_split_isolation"]


@given(extra_values=st.integers(min_value=1, max_value=4))
@settings(
    max_examples=12,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
def test_edge_sensor_quality_rejects_sample_shape_mismatches(
    tmp_path: Path, extra_values: int,
) -> None:
    malformed = _sensor_payload(
        rows=[[0] * (extra_values + 1), [1] * (extra_values + 1)],
    )
    record = _stored_record(
        tmp_path, "shape", "device-a", "train", payload=malformed,
    )

    result = evaluate_quality(
        [record], record_schema="edge_sensor_window", allowed_local_roots=(tmp_path,),
    )

    assert result.passed is False
    assert "shape" in result.checks["payload_semantics"]
