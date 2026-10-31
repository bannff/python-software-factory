"""Single registry and deterministic derivation for CAN adequacy policy."""
from __future__ import annotations

import hashlib
import math
from math import fsum
from typing import Any, Iterable

from .can_evaluation_contracts import (
    CanAdequacyBinding, CanCaseAdequacy, CanEvaluationEvidence,
    CanEvaluationPolicy, CanEvaluatorProvenance, CanMetricRule, CanRunAdequacy,
)
from .can_lifecycle_refs import CanEvalsPointer
from .passport_validation import canonical_json

POLICY_ID = "can.synthetic-sensitivity.classification"
POLICY_VERSION = "1.0"
POLICY_IDENTITY = f"{POLICY_ID}@{POLICY_VERSION}"

_POLICY = CanEvaluationPolicy(
    policy_id=POLICY_ID, policy_version=POLICY_VERSION,
    scope="synthetic_sensitivity", required_split_kind="ordered_holdout",
    min_validation_rows=20, min_positive_rows=5, min_negative_rows=5,
    metric_rules=(
        CanMetricRule(metric="accuracy", operator="gte", threshold=0.70),
        CanMetricRule(metric="precision", operator="gte", threshold=0.60),
        CanMetricRule(metric="recall", operator="gte", threshold=0.60),
        CanMetricRule(metric="f1", operator="gte", threshold=0.60),
        CanMetricRule(metric="auroc", operator="gte", threshold=0.70),
        CanMetricRule(metric="auprc", operator="gte", threshold=0.60),
        CanMetricRule(metric="brier", operator="lte", threshold=0.25),
    ),
    score_metric="f1", promotion_eligible=False,
)
_REGISTRY = {(POLICY_ID, POLICY_VERSION): _POLICY}


def get_policy(policy_id: str = POLICY_ID, version: str = POLICY_VERSION) -> CanEvaluationPolicy:
    """Resolve only explicitly registered policy identities."""
    try:
        return _REGISTRY[(policy_id, version)]
    except KeyError as exc:
        raise ValueError(f"unknown CAN evaluation policy: {policy_id}@{version}") from exc


def policy_digest(policy: CanEvaluationPolicy = _POLICY) -> str:
    payload = policy.model_dump(mode="json")
    return "sha256:" + hashlib.sha256(canonical_json(payload)).hexdigest()


def derive_case(
    *, case_id: str, model_id: str, metrics: dict[str, Any],
    evidence: CanEvaluationEvidence, provenance: CanEvaluatorProvenance,
    policy: CanEvaluationPolicy = _POLICY,
) -> CanCaseAdequacy:
    """Derive one case without allowing malformed evidence to pass."""
    reasons = _evidence_reasons(evidence, policy)
    values: dict[str, float | None] = {}
    states = {}
    for rule in policy.metric_rules:
        value, state = _metric(metrics, rule.metric)
        values[rule.metric] = value
        states[rule.metric] = state
        if state != "valid":
            reasons.append(f"metric_{state}:{rule.metric}")
        elif not _threshold_passes(value, rule):
            direction = "below" if rule.operator == "gte" else "above"
            reasons.append(f"metric_{direction}_threshold:{rule.metric}")
    score = values[policy.score_metric]
    passed = not reasons
    return CanCaseAdequacy(
        case_id=case_id, model_id=model_id, policy_id=policy.policy_id,
        policy_version=policy.policy_version, policy_digest=policy_digest(policy),
        evidence=evidence, evaluator_provenance=provenance,
        metrics=values, metric_states=states, passed=passed,
        score=score if score is not None and 0.0 <= score <= 1.0 else 0.0,
        reason_codes=tuple(reasons),
        promotion_eligible=bool(passed and policy.promotion_eligible),
    )


def derive_run(
    cases: Iterable[CanCaseAdequacy], policy: CanEvaluationPolicy = _POLICY,
) -> CanRunAdequacy:
    """Independently re-derive every case and all aggregate values."""
    rebuilt = tuple(_rederive_case(case, policy) for case in cases)
    if not rebuilt:
        raise ValueError("CAN evaluation requires at least one case")
    passed = sum(case.passed for case in rebuilt)
    total = len(rebuilt)
    average = fsum(case.score for case in rebuilt) / total
    return CanRunAdequacy(
        policy_id=policy.policy_id, policy_version=policy.policy_version,
        policy_digest=policy_digest(policy), scope=policy.scope,
        promotion_eligible=bool(all(case.promotion_eligible for case in rebuilt)),
        verdict="PASS" if passed == total else "FAIL", total_cases=total,
        passed=passed, failed=total - passed, pass_rate=passed / total,
        avg_score=average, cases=rebuilt,
    )


def adequacy_bindings(
    pointer: CanEvalsPointer, run_id: str, adequacy: CanRunAdequacy,
    summary: dict[str, Any],
) -> tuple[CanAdequacyBinding, ...]:
    """Bind each exact case to its pointer and complete authenticated summary."""
    summary_digest = _digest(summary)
    return tuple(CanAdequacyBinding(
        pointer=pointer, run_id=run_id, case_id=case.case_id,
        model_id=case.model_id,
        evaluator_identity=case.evaluator_provenance.evaluator_identity,
        input_digest=case.evaluator_provenance.input_digest,
        case_digest=_digest(case.model_dump(mode="json")),
        policy_id=adequacy.policy_id, policy_version=adequacy.policy_version,
        policy_digest=adequacy.policy_digest, scope=adequacy.scope,
        run_verdict=adequacy.verdict,
        run_promotion_eligible=adequacy.promotion_eligible,
        summary_digest=summary_digest,
    ) for case in adequacy.cases)


def adequacy_binding(
    pointer: CanEvalsPointer, run_id: str, adequacy: CanRunAdequacy,
    summary: dict[str, Any] | None = None,
) -> CanAdequacyBinding:
    """Compatibility helper for a single-case run."""
    bindings = adequacy_bindings(
        pointer, run_id, adequacy,
        summary or {"adequacy": adequacy.model_dump(mode="json")},
    )
    if len(bindings) != 1:
        raise ValueError("singular adequacy binding requires exactly one case")
    return bindings[0]


def _digest(value: dict[str, Any]) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value)).hexdigest()


def _evidence_reasons(evidence, policy) -> list[str]:
    reasons = []
    if evidence.split_kind != policy.required_split_kind:
        reasons.append("seeded_fallback_not_held_out")
    if evidence.validation_count < policy.min_validation_rows:
        reasons.append("validation_rows_below_minimum")
    if evidence.positive_count == 0 or evidence.negative_count == 0:
        reasons.append("validation_single_class")
    if evidence.positive_count < policy.min_positive_rows:
        reasons.append("positive_rows_below_minimum")
    if evidence.negative_count < policy.min_negative_rows:
        reasons.append("negative_rows_below_minimum")
    return reasons


def _metric(metrics: dict[str, Any], name: str) -> tuple[float | None, str]:
    if name not in metrics:
        return None, "missing"
    raw = metrics[name]
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        return None, "nonfinite"
    value = float(raw)
    if not math.isfinite(value):
        return None, "nonfinite"
    if not 0.0 <= value <= 1.0:
        return value, "out_of_range"
    return value, "valid"


def _threshold_passes(value: float | None, rule: CanMetricRule) -> bool:
    assert value is not None
    return value >= rule.threshold if rule.operator == "gte" else value <= rule.threshold


def _rederive_case(case: CanCaseAdequacy, policy: CanEvaluationPolicy) -> CanCaseAdequacy:
    raw = {}
    for name, state in case.metric_states.items():
        value = case.metrics.get(name)
        if state in {"valid", "out_of_range"}:
            raw[name] = value
        elif state == "nonfinite":
            raw[name] = math.nan
    return derive_case(
        case_id=case.case_id, model_id=case.model_id, metrics=raw,
        evidence=case.evidence, provenance=case.evaluator_provenance, policy=policy,
    )


__all__ = [
    "POLICY_ID", "POLICY_IDENTITY", "POLICY_VERSION", "adequacy_binding",
    "adequacy_bindings", "derive_case", "derive_run", "get_policy", "policy_digest",
]
