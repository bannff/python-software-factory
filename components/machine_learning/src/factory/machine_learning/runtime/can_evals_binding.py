"""Fail-closed MCP bindings to Evals immutable record verification."""
from __future__ import annotations

from typing import Any

from .can_evaluation_contracts import (
    CAN_EVALUATOR_IDENTITY, CanCaseAdequacy, CanRunAdequacy,
    CanVerifiedEvaluationRecord,
)
from .can_evaluation_policy import (
    adequacy_bindings, derive_case, derive_run, get_policy,
)
from .can_lifecycle_refs import CanEvalsPointer
from .passport_validation import canonical_json

EVALS_TOOL = "evals_verify_record_pointer"
EVALS_TOOL_IDENTITY = "evals.verify-record-pointer@v1"
MlEvalsRecordPointer = CanEvalsPointer


def verify_evaluation_pointers(
    invoker: Any, pointers: list[dict[str, Any]] | tuple[CanEvalsPointer, ...],
) -> tuple[CanEvalsPointer, ...]:
    """Preserve legacy exact six-field pointer verification behavior."""
    verified = _typed_pointers(pointers)
    for pointer in verified:
        value = pointer.model_dump(mode="json")
        response = _unwrap_tool_result(invoker(EVALS_TOOL, **value))
        _require_verified(response, value)
    return verified


def verify_evaluation_records(
    invoker: Any, pointers: list[dict[str, Any]] | tuple[CanEvalsPointer, ...],
) -> tuple[CanVerifiedEvaluationRecord, ...]:
    """Re-derive cases and aggregates from authenticated raw Evals facts."""
    records = []
    for pointer in _typed_pointers(pointers):
        value = pointer.model_dump(mode="json")
        response = _unwrap_tool_result(invoker(EVALS_TOOL, **value))
        _require_verified(response, value)
        run_id, summary = _identity(response)
        try:
            adequacy = _derive_authenticated(response, summary)
            bindings = adequacy_bindings(pointer, run_id, adequacy, summary)
        except Exception as exc:
            raise ValueError(f"Evals adequacy verification failed: {exc}") from exc
        records.append(CanVerifiedEvaluationRecord(
            pointer=pointer, run_id=run_id, adequacy=adequacy, bindings=bindings,
        ))
    return tuple(records)


def _derive_authenticated(response: dict[str, Any], summary: dict[str, Any]) -> CanRunAdequacy:
    raw_cases = response.get("case_results")
    if not isinstance(raw_cases, list) or not raw_cases:
        raise ValueError("authenticated case_results are malformed")
    rebuilt = []
    for raw in raw_cases:
        if not isinstance(raw, dict):
            raise ValueError("authenticated case_result is malformed")
        observed = CanCaseAdequacy.model_validate_json(canonical_json(raw), strict=True)
        policy = get_policy(observed.policy_id, observed.policy_version)
        metrics = {key: value for key, value in observed.metrics.items() if value is not None}
        derived = derive_case(
            case_id=observed.case_id, model_id=observed.model_id,
            metrics=metrics, evidence=observed.evidence,
            provenance=observed.evaluator_provenance, policy=policy,
        )
        if derived.model_dump(mode="json") != raw:
            raise ValueError("authenticated case is not canonical policy derivation")
        rebuilt.append(derived)
    policy = get_policy(rebuilt[0].policy_id, rebuilt[0].policy_version)
    adequacy = derive_run(rebuilt, policy)
    _require_top_level(response, adequacy)
    raw_adequacy = summary.get("adequacy")
    if raw_adequacy != adequacy.model_dump(mode="json"):
        raise ValueError("summary.adequacy is not the canonical raw-facts projection")
    return adequacy


def _require_top_level(response: dict[str, Any], adequacy: CanRunAdequacy) -> None:
    expected = {
        "case_results": [case.model_dump(mode="json") for case in adequacy.cases],
        "case_scores": [case.score for case in adequacy.cases],
        "verdict": adequacy.verdict,
        "pass_rate": adequacy.pass_rate,
        "avg_score": adequacy.avg_score,
        "total_cases": adequacy.total_cases,
        "passed_cases": adequacy.passed,
        "failed_cases": adequacy.failed,
        "evaluators_used": [CAN_EVALUATOR_IDENTITY],
    }
    for field, value in expected.items():
        if response.get(field) != value:
            raise ValueError(f"authenticated {field} is not canonical")


def _identity(response: Any) -> tuple[str, dict[str, Any]]:
    run_id = response.get("run_id") if isinstance(response, dict) else None
    summary = response.get("summary") if isinstance(response, dict) else None
    if not isinstance(run_id, str) or not run_id or run_id != run_id.strip():
        raise ValueError("Evals verifier returned a malformed run_id")
    if not isinstance(summary, dict):
        raise ValueError("Evals verifier returned malformed summary")
    return run_id, summary


def _typed_pointers(pointers):
    if not pointers:
        raise ValueError("at least one verified Evals record pointer is required")
    return tuple(CanEvalsPointer.model_validate(pointer) for pointer in pointers)


def _unwrap_tool_result(response: Any) -> Any:
    """Accept a legacy raw result or the public ToolResult v1 transport."""
    if not isinstance(response, dict) or "schema_version" not in response:
        return response
    if response.get("schema_version") != "v1" or response.get("ok") is not True:
        reason = response.get("error", "unknown ToolResult failure")
        raise ValueError(f"Evals record pointer verification failed: {reason}")
    return response.get("data")


def _require_verified(response: Any, pointer: dict[str, Any]) -> None:
    if not isinstance(response, dict) or response.get("verified") is not True:
        reason = response.get("reason") if isinstance(response, dict) else response
        raise ValueError(f"Evals record pointer verification failed: {reason}")
    if response.get("pointer") != pointer:
        raise ValueError("Evals verifier returned a different pointer")


__all__ = [
    "CanEvalsPointer", "EVALS_TOOL", "EVALS_TOOL_IDENTITY",
    "MlEvalsRecordPointer", "verify_evaluation_pointers",
    "verify_evaluation_records",
]
