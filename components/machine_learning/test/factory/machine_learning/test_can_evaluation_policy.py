"""Focused adequacy policy and evaluation-request acceptance tests."""
from __future__ import annotations

import hashlib
import math

import pytest

from factory.machine_learning.runtime.can_evaluation_contracts import (
    CanEvaluationEvidence, CanEvaluatorProvenance,
)
from factory.machine_learning.runtime.can_evaluation_policy import (
    POLICY_IDENTITY, derive_case, derive_run, get_policy, policy_digest,
)
from factory.machine_learning.runtime.can_evaluation_request import (
    build_evaluation_record_request,
)
from factory.machine_learning.runtime.can_lifecycle_results import (
    CanEvaluationRecordRequest,
)
from factory.machine_learning.runtime.passport_validation import canonical_json

GOOD = {
    "accuracy": 0.80, "precision": 0.70, "recall": 0.75, "f1": 0.72,
    "auroc": 0.82, "auprc": 0.73, "brier": 0.18,
}
ORDERED = CanEvaluationEvidence(
    scope="synthetic_sensitivity", split_kind="ordered_holdout",
    validation_count=30, positive_count=15, negative_count=15,
)
PROVENANCE = CanEvaluatorProvenance(
    schema="evals.can-model-evidence", version="1.0",
    evaluator_identity="evals.can-model@v1", input_digest="sha256:" + "b" * 64,
)


def _case(metrics=None, evidence=ORDERED, case_id="0x1"):
    return derive_case(
        case_id=case_id, model_id=f"model-{case_id}",
        metrics=GOOD if metrics is None else metrics, evidence=evidence,
        provenance=PROVENANCE,
    )


def test_policy_identity_digest_and_synthetic_ineligibility_are_canonical():
    policy = get_policy()
    expected = "sha256:" + hashlib.sha256(canonical_json(
        policy.model_dump(mode="json"),
    )).hexdigest()
    assert policy.identity == POLICY_IDENTITY
    assert policy_digest() == expected
    adequacy = derive_run((_case(),))
    assert adequacy.verdict == "PASS"
    assert adequacy.passed == 1 and adequacy.failed == 0
    assert adequacy.pass_rate == 1.0 and adequacy.avg_score == GOOD["f1"]
    assert adequacy.promotion_eligible is False
    request = build_evaluation_record_request(
        dataset_terminal={"vehicle_id": "truck-1"}, portfolio=[_row("0x1", GOOD)],
        experiment_name="policy-pass-test",
    )
    assert request["verdict"] == "PASS"
    assert request["summary"]["adequacy"]["promotion_eligible"] is False


@pytest.mark.parametrize(("metrics", "reason"), [
    ({key: value for key, value in GOOD.items() if key != "auroc"},
     "metric_missing:auroc"),
    ({**GOOD, "f1": math.nan}, "metric_nonfinite:f1"),
    ({**GOOD, "accuracy": 1.1}, "metric_out_of_range:accuracy"),
    ({**GOOD, "precision": 0.59}, "metric_below_threshold:precision"),
    ({**GOOD, "brier": 0.26}, "metric_above_threshold:brier"),
])
def test_metric_failures_are_explicit_and_fail_closed(metrics, reason):
    case = _case(metrics)
    assert case.passed is False and reason in case.reason_codes
    assert 0.0 <= case.score <= 1.0


@pytest.mark.parametrize(("evidence", "reason"), [
    (CanEvaluationEvidence(
        scope="synthetic_sensitivity", split_kind="seeded_shuffle_sensitivity",
        validation_count=30, positive_count=15, negative_count=15,
    ), "seeded_fallback_not_held_out"),
    (CanEvaluationEvidence(
        scope="synthetic_sensitivity", split_kind="ordered_holdout",
        validation_count=19, positive_count=9, negative_count=10,
    ), "validation_rows_below_minimum"),
    (CanEvaluationEvidence(
        scope="synthetic_sensitivity", split_kind="ordered_holdout",
        validation_count=20, positive_count=4, negative_count=16,
    ), "positive_rows_below_minimum"),
    (CanEvaluationEvidence(
        scope="synthetic_sensitivity", split_kind="ordered_holdout",
        validation_count=20, positive_count=20, negative_count=0,
    ), "validation_single_class"),
])
def test_split_and_support_failures_are_explicit(evidence, reason):
    assert reason in _case(evidence=evidence).reason_codes


def test_run_counts_and_request_failure_are_derived_from_cases():
    passing = _case(case_id="0x1")
    failing = _case({**GOOD, "recall": 0.1}, case_id="0x2")
    adequacy = derive_run((passing, failing))
    assert adequacy.verdict == "FAIL"
    assert (adequacy.total_cases, adequacy.passed, adequacy.failed) == (2, 1, 1)
    assert adequacy.pass_rate == 0.5

    rows = [_row("0x1", GOOD), _row("0x2", {**GOOD, "recall": 0.1})]
    request = build_evaluation_record_request(
        dataset_terminal={"vehicle_id": "truck-1"}, portfolio=rows,
        experiment_name="policy-test",
    )
    validated = CanEvaluationRecordRequest.model_validate(request)
    assert validated.verdict == "FAIL"
    assert validated.passed == 1 and validated.failed_cases == 1
    assert validated.pass_rate == 0.5
    assert validated.summary["adequacy"]["verdict"] == "FAIL"
    assert validated.evaluators_used == ["evals.can-model@v1"]


def _row(can_id: str, metrics: dict) -> dict:
    return {
        "can_id": can_id, "job_id": f"model-{can_id}", "metrics": metrics,
        "evaluation_evidence": ORDERED.model_dump(mode="json"),
        "evaluator_provenance": PROVENANCE.model_dump(mode="json"),
        "model_path": f"file:///{can_id}", "contract_digest": "a" * 64,
    }
