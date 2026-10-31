"""Deterministic Evals request projection from trusted CAN training output."""
from __future__ import annotations

from typing import Any

from .can_evaluation_contracts import (
    CanEvaluationEvidence, CanEvaluatorProvenance,
)
from .can_evaluation_policy import derive_case, derive_run


def build_evaluation_record_request(
    *, dataset_terminal: dict[str, Any], portfolio: list[dict[str, Any]],
    experiment_name: str,
) -> dict[str, Any]:
    """Derive every non-identity ``evals_record_run`` argument from policy."""
    cases = tuple(_case(row) for row in portfolio)
    adequacy = derive_run(cases)
    scores = [case.score for case in adequacy.cases]
    vehicle_id = str(dataset_terminal["vehicle_id"])
    model_ids = [str(row["job_id"]) for row in portfolio]
    evaluator_ids = [case.evaluator_provenance.evaluator_identity for case in cases]
    if len(set(evaluator_ids)) != 1:
        raise ValueError("CAN evaluation cases use conflicting evaluator identities")
    return {
        "experiment_name": experiment_name or f"can-lifecycle:{vehicle_id}",
        "verdict": adequacy.verdict,
        "pass_rate": adequacy.pass_rate,
        "avg_score": adequacy.avg_score,
        "total_cases": adequacy.total_cases,
        "passed": adequacy.passed,
        "case_results": [case.model_dump(mode="json") for case in adequacy.cases],
        "evaluators_used": [evaluator_ids[0]],
        "agent": {"id": "ml-can-lifecycle", "model_family": "lightgbm"},
        "timestamp": "",
        "source": "ml_can_lifecycle",
        "failed_cases": adequacy.failed,
        "duration_ms": 0.0,
        "case_scores": scores,
        "summary": {
            "vehicle_id": vehicle_id, "model_ids": model_ids,
            "total_cases": adequacy.total_cases, "passed": adequacy.passed,
            "failed": adequacy.failed, "pass_rate": adequacy.pass_rate,
            "overall_score": adequacy.avg_score,
            "adequacy": adequacy.model_dump(mode="json"),
        },
        "artifacts": {
            str(row["can_id"]): {
                "model_uri": str(row["model_path"]),
                "model_id": str(row["job_id"]),
                "contract_digest": str(row["contract_digest"]),
            } for row in portfolio
        },
        "record_kind": "evaluation_run",
        "terminal_state": "completed",
        "score_projection": {},
    }


def _case(row: dict[str, Any]):
    evidence = CanEvaluationEvidence.model_validate(row["evaluation_evidence"])
    provenance = CanEvaluatorProvenance.model_validate(row["evaluator_provenance"])
    return derive_case(
        case_id=str(row["can_id"]), model_id=str(row["job_id"]),
        metrics=dict(row["metrics"]), evidence=evidence, provenance=provenance,
    )


__all__ = ["build_evaluation_record_request"]
