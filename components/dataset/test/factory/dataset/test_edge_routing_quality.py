"""Contract checks for reviewed live-SDK edge routing evidence."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from factory.dataset.runtime.quality import evaluate_quality


def _evidence(root: Path, record_id: str, name: str, payload: dict) -> dict[str, str]:
    content = json.dumps(payload, sort_keys=True).encode()
    path = root / f"{record_id}-{name}.json"
    path.write_bytes(content)
    return {"uri": path.as_uri(), "sha256": hashlib.sha256(content).hexdigest()}


def stored_routing_example(root: Path, record_id: str, split: str) -> dict:
    """Synthetic contract fixture; never treated as real training evidence."""
    candidate_id = f"device-{record_id}"
    candidate = {
        "candidate_id": candidate_id,
        "capability_id": f"cap-{record_id}",
        "capabilities": ("review",),
        "role": "reviewer", "model_id": "tiny-reviewer",
        "model_artifact_sha256": "d" * 64,
        "observed_at": "2026-01-01T00:00:00Z",
        "expires_at": "2026-01-01T00:01:00Z",
        "status": "available", "battery_pct": 80,
        "cpu_utilization_pct": 10, "memory_available_mib": 128,
        "estimated_link_latency_ms": 15,
    }
    common = {"schema_version": "1.0", "record_id": record_id}
    source_id = f"source-{record_id}"
    source_ref = _evidence(root, record_id, "source", {
        **common, "kind": "source_event", "source_event_id": source_id,
        "group_id": f"episode-{record_id}",
        "session_id": f"session-{record_id}", "task_id": f"task-{record_id}",
        "source_event_at": "2026-01-01T00:00:00Z",
    })
    snapshot_ref = _evidence(root, record_id, "snapshot", {
        **common, "kind": "candidate_snapshot",
        "decision_at": "2026-01-01T00:00:01Z",
        "candidates": [candidate], "eligible_candidate_ids": [candidate_id],
    })
    execution_ref = _evidence(root, record_id, "execution", {
        **common, "kind": "route_execution", "source_event_id": source_id,
        "candidate_id": candidate_id, "selected_at": "2026-01-01T00:00:02Z",
        "selection_propensity": 1.0,
    })
    outcome_ref = _evidence(root, record_id, "outcome", {
        **common, "kind": "route_outcome", "run_id": f"run-{record_id}",
        "sdk_version": "5.2.0", "candidate_id": candidate_id,
        "observed_at": "2026-01-01T00:00:03Z",
        "succeeded": record_id != "test",
        "execution_sha256": execution_ref["sha256"],
    })
    adjudication_ref = _evidence(root, record_id, "review", {
        **common, "kind": "route_adjudication", "reviewer_ref": "reviewer-a",
        "verdict": "accepted", "reviewed_at": "2026-01-01T00:00:04Z",
        "outcome_sha256": outcome_ref["sha256"],
    })
    return {
        "schema_version": "1.0", "record_id": record_id, "split": split,
        "features": {
            "group_id": f"episode-{record_id}",
            "session_id": f"session-{record_id}",
            "task_id": f"task-{record_id}",
            "source_event_id": source_id,
            "source_event_ref": source_ref,
            "source_event_at": "2026-01-01T00:00:00Z",
            "decision_at": "2026-01-01T00:00:01Z",
            "task_kind": "review-alert",
            "policy_version": "p1",
            "policy_sha256": "a" * 64,
            "reducer_sha256": "b" * 64,
            "scenario_sha256": "c" * 64,
            "required_capabilities": ("review",),
            "candidate_snapshot_ref": snapshot_ref,
            "candidates": (candidate,),
            "eligible_candidate_ids": (candidate_id,),
        },
        "executed_route": {
            "candidate_id": candidate_id,
            "selection_propensity": 1.0,
            "selected_at": "2026-01-01T00:00:02Z",
            "execution_ref": execution_ref,
        },
        "outcome": {
            "outcome_ref": outcome_ref,
            "run_id": f"run-{record_id}",
            "sdk_version": "5.2.0",
            "provenance_kind": "ditto_sdk_live",
            "observed_at": "2026-01-01T00:00:03Z",
            "succeeded": record_id != "test",
            "review": {
                "reviewer_ref": "reviewer-a",
                "adjudication_ref": adjudication_ref,
                "reviewed_at": "2026-01-01T00:00:04Z",
                "verdict": "accepted",
            },
        },
    }


def _three_records(root: Path) -> list[dict]:
    return [
        stored_routing_example(root, "train", "train"),
        stored_routing_example(root, "validation", "validation"),
        stored_routing_example(root, "test", "test"),
    ]


def test_complete_typed_fixture_still_lacks_trusted_live_provenance(tmp_path: Path) -> None:
    result = evaluate_quality(_three_records(tmp_path), record_schema="edge_routing_example")
    assert not result.passed
    assert result.checks["evidence_integrity"].startswith("passed:")
    assert result.checks["evidence_semantics"].startswith("passed:")
    assert result.checks["reviewed_label_structure"].startswith("passed:")
    assert result.checks["trusted_run_provenance"].startswith("failed:")


def test_empty_records_have_no_labels(tmp_path: Path) -> None:
    result = evaluate_quality([], record_schema="edge_routing_example")
    assert not result.passed
    assert result.checks["record_count"] == "failed: 0 records"
    assert "no reviewed" in result.checks["reviewed_label_structure"]


@pytest.mark.parametrize("change", ["duplicate", "collision"])
def test_duplicate_ids_and_same_id_different_content_fail(tmp_path: Path, change: str) -> None:
    records = _three_records(tmp_path)
    repeated = json.loads(json.dumps(records[0]))
    if change == "collision":
        repeated["features"]["task_kind"] = "different-task"
    records.append(repeated)
    result = evaluate_quality(records, record_schema="edge_routing_example")
    assert not result.passed
    assert "train" in result.checks["record_ids"]
    assert ("train" in result.checks["record_id_content_collisions"]) == (change == "collision")
