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

from .test_edge_routing_contracts import _example

def test_dispatch_and_readiness_require_reviewed_live_outcomes_across_splits() -> None:
    records = [_example(split=split) for split in ("train", "validation", "test")]
    validated = list(dispatch_validator(records, record_schema="edge_routing_example"))
    readiness = routing_dataset_readiness(validated)
    assert readiness.status == "quality_blocked"
    assert readiness.training_allowed is False
    assert readiness.reviewed_label_count == 3
    assert "trusted_run_provenance" in readiness.reason

    duplicate = routing_dataset_readiness([*records, deepcopy(records[0])])
    assert duplicate.reviewed_label_count == 3

    records[2]["outcome"]["review"] = None
    unreviewed = routing_dataset_readiness(
        dispatch_validator(records, record_schema="edge_routing_example"),
    )
    assert unreviewed.status == "no_labels"
    assert unreviewed.training_allowed is False
    assert "test" in unreviewed.reason

def test_readiness_rejects_bad_refs_and_leaky_splits() -> None:
    records = [_example(split=split) for split in ("train", "validation", "test")]
    records[0]["features"]["source_event_ref"]["sha256"] = "0" * 64
    readiness = routing_dataset_readiness(records)
    assert readiness.status == "quality_blocked"
    assert readiness.training_allowed is False
    assert "evidence_integrity" in readiness.reason
    assert "session_split_isolation" in readiness.reason

def test_unselected_candidates_are_censored() -> None:
    record = _example()
    record["outcome"]["candidate_results"] = {"peer-b": False}
    with pytest.raises(ValueError):
        EdgeRoutingExample.model_validate(record)

    record = _example()
    record["executed_route"] = None
    record["outcome"] = None
    assert routing_dataset_readiness([record]).status == "no_labels"

def test_simulated_or_rejected_outcomes_are_not_trainable() -> None:
    records = [_example(split=split) for split in ("train", "validation", "test")]
    records[0]["outcome"]["provenance_kind"] = "simulated"
    records[1]["outcome"]["review"]["verdict"] = "rejected"
    readiness = routing_dataset_readiness(records)
    assert readiness.status == "no_labels"
    assert readiness.reviewed_label_count == 1
