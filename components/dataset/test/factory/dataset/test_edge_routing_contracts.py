"""Boundary and readiness tests for observed edge routing examples."""

from __future__ import annotations

from copy import deepcopy

import pytest
from hypothesis import given, strategies as st

from factory.dataset.runtime.edge_routing_contracts import (
    EdgeRoutingExample,
    routing_dataset_readiness,
)
from factory.dataset.runtime.validation import (
    dispatch_validator,
    validate_edge_routing_records,
)


DIGEST = "a" * 64


def _ref(name: str) -> dict[str, str]:
    return {"uri": f"file:///evidence/{name}.json", "sha256": DIGEST}


def _example(*, split: str = "train", reviewed: bool = True) -> dict:
    outcome = {
        "outcome_ref": _ref("outcome"),
        "run_id": "sdk-run-1",
        "sdk_version": "5.2.0",
        "provenance_kind": "ditto_sdk_live",
        "observed_at": "2026-09-30T12:00:03Z",
        "succeeded": True,
        "review": {
            "reviewer_ref": "reviewer-1",
            "adjudication_ref": _ref("adjudication"),
            "reviewed_at": "2026-09-30T12:00:04Z",
            "verdict": "accepted",
        } if reviewed else None,
    }
    return {
        "schema_version": "1.0",
        "record_id": f"routing-{split}-1",
        "split": split,
        "features": {
            "group_id": f"group-{split}",
            "session_id": "session-1",
            "task_id": f"task-{split}",
            "source_event_id": f"event-{split}",
            "source_event_ref": _ref("source"),
            "source_event_at": "2026-09-30T11:59:59Z",
            "decision_at": "2026-09-30T12:00:00Z",
            "task_kind": "inspect-image",
            "policy_version": "policy-v1",
            "policy_sha256": DIGEST,
            "reducer_sha256": DIGEST,
            "scenario_sha256": DIGEST,
            "required_capabilities": ["vision"],
            "candidate_snapshot_ref": _ref("candidates"),
            "candidates": [
                {
                    "candidate_id": "peer-a", "capability_id": "cap-a",
                    "capabilities": ["vision"], "role": "camera",
                    "model_id": "vision-v1", "model_artifact_sha256": DIGEST,
                    "observed_at": "2026-09-30T11:59:58Z",
                    "expires_at": "2026-09-30T12:01:00Z", "status": "available",
                    "battery_pct": 80, "cpu_utilization_pct": 10,
                    "memory_available_mib": 256, "estimated_link_latency_ms": 30,
                },
                {
                    "candidate_id": "peer-b", "capability_id": "cap-b",
                    "capabilities": ["vision"], "role": "camera",
                    "model_id": "vision-v1", "model_artifact_sha256": DIGEST,
                    "observed_at": "2026-09-30T11:59:58Z",
                    "expires_at": "2026-09-30T12:01:00Z", "status": "available",
                    "battery_pct": 40, "cpu_utilization_pct": 70,
                    "memory_available_mib": 128, "estimated_link_latency_ms": 50,
                },
            ],
            "eligible_candidate_ids": ["peer-a", "peer-b"],
        },
        "executed_route": {
            "candidate_id": "peer-a", "selection_propensity": 0.5,
            "selected_at": "2026-09-30T12:00:01Z",
            "execution_ref": _ref("execution"),
        },
        "outcome": outcome,
    }


def test_contract_separates_predecision_features_from_route_and_outcome() -> None:
    record = EdgeRoutingExample.model_validate(_example())
    assert record.features.candidates[0].candidate_id == "peer-a"
    assert record.executed_route is not None
    assert record.outcome is not None
    assert "succeeded" not in record.features.model_dump()
    assert "executed_route" not in record.features.model_dump()
    assert record.features.decision_at.utcoffset().total_seconds() == 0


@pytest.mark.parametrize("path,value", [
    (("features", "winner"), "peer-a"),
    (("features", "candidates", 0, "result"), "success"),
    (("features", "candidate_snapshot_ref", "unknown"), "bad"),
    (("features", "policy_sha256"), "bad"),
    (("features", "source_event_at"), "2026-09-30T12:00:01Z"),
    (("features", "candidates", 0, "observed_at"), "2026-09-30T12:00:01Z"),
    (("features", "eligible_candidate_ids"), ["peer-c"]),
    (("executed_route", "candidate_id"), "peer-c"),
    (("executed_route", "selection_propensity"), 0),
    (("executed_route", "selected_at"), "2026-09-30T12:01:00Z"),
    (("outcome", "observed_at"), "2026-09-30T12:00:00Z"),
    (("outcome", "review", "reviewed_at"), "2026-09-30T12:00:00Z"),
])
def test_invalid_and_leaky_records_are_rejected(path: tuple, value: object) -> None:
    record = _example()
    target = record
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    with pytest.raises((ValueError, TypeError)):
        EdgeRoutingExample.model_validate(record)


def test_noneligible_and_duplicate_candidates_are_rejected() -> None:
    unavailable = _example()
    unavailable["features"]["candidates"][0]["status"] = "unavailable"
    with pytest.raises(ValueError):
        EdgeRoutingExample.model_validate(unavailable)

    duplicate = _example()
    duplicate["features"]["candidates"][1]["candidate_id"] = "peer-a"
    with pytest.raises(ValueError):
        EdgeRoutingExample.model_validate(duplicate)

    duplicate_capability = _example()
    duplicate_capability["features"]["candidates"][1]["capability_id"] = "cap-a"
    with pytest.raises(ValueError):
        EdgeRoutingExample.model_validate(duplicate_capability)


def test_record_is_immutable_and_utc_is_required() -> None:
    record = EdgeRoutingExample.model_validate(_example())
    with pytest.raises(ValueError):
        record.features.candidates[0].battery_pct = 0

    for timestamp in ("2026-09-30T12:00:00", "2026-09-30T08:00:00-04:00"):
        raw = _example()
        raw["features"]["decision_at"] = timestamp
        with pytest.raises(ValueError):
            EdgeRoutingExample.model_validate(raw)


@given(st.floats(allow_nan=True, allow_infinity=True))
def test_selection_propensity_is_finite_probability(propensity: float) -> None:
    record = _example()
    record["executed_route"]["selection_propensity"] = propensity
    if 0 < propensity <= 1:
        assert EdgeRoutingExample.model_validate(record).executed_route.selection_propensity == propensity
    else:
        with pytest.raises(ValueError):
            EdgeRoutingExample.model_validate(record)


def test_duplicate_identity_and_different_content_fail_closed() -> None:
    original = _example()
    repeated = list(validate_edge_routing_records([original, deepcopy(original)]))
    assert len(repeated) == 2  # quality must see and reject duplicate source rows
    assert repeated[0] == repeated[1]
    changed = deepcopy(original)
    changed["outcome"]["succeeded"] = False
    with pytest.raises(ValueError, match="same record_id.*different content"):
        list(validate_edge_routing_records([original, changed]))
    changed = deepcopy(original)
    changed["record_id"] = "routing-other"
    with pytest.raises(ValueError, match="same decision identity"):
        list(validate_edge_routing_records([original, changed]))
    with pytest.raises(ValueError, match="same decision identity"):
        routing_dataset_readiness([original, changed])
