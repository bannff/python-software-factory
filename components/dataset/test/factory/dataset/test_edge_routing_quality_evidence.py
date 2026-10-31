"""Contract checks for reviewed live-SDK edge routing evidence."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from factory.dataset.runtime.quality import evaluate_quality

from .test_edge_routing_quality import _three_records
from .test_edge_routing_quality import stored_routing_example

@pytest.mark.parametrize("field,check", [
    ("group_id", "episode_split_isolation"),
    ("session_id", "session_split_isolation"),
    ("task_id", "task_split_isolation"),
    ("source_event_id", "source_event_split_isolation"),
])
def test_identity_cannot_cross_splits(tmp_path: Path, field: str, check: str) -> None:
    records = _three_records(tmp_path)
    records[1]["features"][field] = records[0]["features"][field]
    result = evaluate_quality(records, record_schema="edge_routing_example")
    assert not result.passed
    assert result.checks[check].startswith("failed:")

@pytest.mark.parametrize("path,check", [
    (("features", "source_event_ref"), "source_digest_split_isolation"),
    (("features", "candidate_snapshot_ref"), "candidate_snapshot_split_isolation"),
    (("executed_route", "execution_ref"), "execution_digest_split_isolation"),
    (("outcome", "outcome_ref"), "outcome_digest_split_isolation"),
    (("outcome", "review", "adjudication_ref"), "adjudication_digest_split_isolation"),
])
def test_content_digest_cannot_cross_splits(
    tmp_path: Path, path: tuple[str, ...], check: str,
) -> None:
    records = _three_records(tmp_path)
    first, second = records[0], records[1]
    for part in path[:-1]:
        first, second = first[part], second[part]
    second[path[-1]] = first[path[-1]]
    result = evaluate_quality(records, record_schema="edge_routing_example")
    assert not result.passed
    assert result.checks[check].startswith("failed:")

@pytest.mark.parametrize("path", [
    ("features", "source_event_ref"),
    ("features", "candidate_snapshot_ref"),
    ("executed_route", "execution_ref"),
    ("outcome", "outcome_ref"),
    ("outcome", "review", "adjudication_ref"),
])
def test_evidence_bytes_must_match_content_digest(
    tmp_path: Path, path: tuple[str, ...],
) -> None:
    records = _three_records(tmp_path)
    ref = records[0]
    for part in path:
        ref = ref[part]
    Path(ref["uri"].removeprefix("file://")).write_bytes(b"tampered")
    result = evaluate_quality(records, record_schema="edge_routing_example")
    assert not result.passed
    assert "train" in result.checks["evidence_integrity"]

def test_symlinked_evidence_is_rejected(tmp_path: Path) -> None:
    records = _three_records(tmp_path)
    target = Path(records[0]["outcome"]["outcome_ref"]["uri"].removeprefix("file://"))
    alias = tmp_path / "outcome-alias.json"
    alias.symlink_to(target)
    records[0]["outcome"]["outcome_ref"]["uri"] = alias.as_uri()
    result = evaluate_quality(records, record_schema="edge_routing_example")
    assert not result.passed
    assert "train" in result.checks["evidence_integrity"]

@pytest.mark.parametrize("payload", [b"not JSON", b'{"id":1,"id":2}', b"[]"])
def test_referenced_evidence_must_be_unambiguous_json_object(
    tmp_path: Path, payload: bytes,
) -> None:
    records = _three_records(tmp_path)
    ref = records[0]["outcome"]["review"]["adjudication_ref"]
    Path(ref["uri"].removeprefix("file://")).write_bytes(payload)
    ref["sha256"] = hashlib.sha256(payload).hexdigest()
    result = evaluate_quality(records, record_schema="edge_routing_example")
    assert not result.passed
    assert "train" in result.checks["evidence_integrity"]

@pytest.mark.parametrize("path,field,replacement", [
    (("features", "source_event_ref"), "record_id", "other-record"),
    (("features", "source_event_ref"), "source_event_id", "other-event"),
    (("features", "candidate_snapshot_ref"), "eligible_candidate_ids", []),
    (("features", "candidate_snapshot_ref"), "candidates", []),
    (("executed_route", "execution_ref"), "candidate_id", "other-device"),
    (("executed_route", "execution_ref"), "selected_at", "2026-01-01T00:00:03Z"),
    (("outcome", "outcome_ref"), "run_id", "other-run"),
    (("outcome", "outcome_ref"), "sdk_version", "0.0.0"),
    (("outcome", "outcome_ref"), "succeeded", False),
    (("outcome", "outcome_ref"), "execution_sha256", "0" * 64),
    (("outcome", "review", "adjudication_ref"), "verdict", "rejected"),
    (("outcome", "review", "adjudication_ref"), "reviewer_ref", "other-reviewer"),
    (("outcome", "review", "adjudication_ref"), "reviewed_at", "2026-01-01T00:00:05Z"),
    (("outcome", "review", "adjudication_ref"), "outcome_sha256", "0" * 64),
])
def test_content_addressed_but_semantically_unrelated_payload_is_rejected(
    tmp_path: Path, path: tuple[str, ...], field: str, replacement: object,
) -> None:
    records = _three_records(tmp_path)
    ref = records[0]
    for part in path:
        ref = ref[part]
    evidence_path = Path(ref["uri"].removeprefix("file://"))
    payload = json.loads(evidence_path.read_bytes())
    payload[field] = replacement
    changed = json.dumps(payload, sort_keys=True).encode()
    evidence_path.write_bytes(changed)
    ref["sha256"] = hashlib.sha256(changed).hexdigest()
    result = evaluate_quality(records, record_schema="edge_routing_example")
    assert not result.passed
    assert result.checks["evidence_integrity"].startswith("passed:")
    assert "train" in result.checks["evidence_semantics"]

@pytest.mark.parametrize("change", ["censored", "simulated", "rejected"])
def test_censored_or_nonreviewed_outcomes_never_become_negative_labels(
    tmp_path: Path, change: str,
) -> None:
    records = _three_records(tmp_path)
    if change == "censored":
        records[0]["outcome"] = None
    elif change == "simulated":
        records[0]["outcome"]["provenance_kind"] = "simulated"
    else:
        records[0]["outcome"]["review"]["verdict"] = "rejected"
    result = evaluate_quality(records, record_schema="edge_routing_example")
    assert not result.passed
    assert "train" in result.checks["reviewed_label_structure"]

@pytest.mark.parametrize("change", ["ineligible", "early_route", "early_outcome"])
def test_route_and_time_invariants_fail_at_schema_boundary(
    tmp_path: Path, change: str,
) -> None:
    records = _three_records(tmp_path)
    if change == "ineligible":
        records[0]["features"]["eligible_candidate_ids"] = ()
    elif change == "early_route":
        records[0]["executed_route"]["selected_at"] = "2025-12-31T23:59:59Z"
    else:
        records[0]["outcome"]["observed_at"] = "2025-12-31T23:59:59Z"
    result = evaluate_quality(records, record_schema="edge_routing_example")
    assert not result.passed
    assert result.checks["schema"].startswith("failed:")
