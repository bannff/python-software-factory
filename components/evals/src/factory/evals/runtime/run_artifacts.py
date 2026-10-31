"""Durable, duplicate-safe artifacts for completed simulation reports."""
from __future__ import annotations

import json
from typing import Any

from .ports import ExperimentReport

ARTIFACTS_SCHEMA_VERSION = 1


def json_safe_copy(value: Any) -> Any:
    """Return only JSON values, refusing NaN and live runtime objects."""
    return json.loads(json.dumps(value, allow_nan=False))


def _evidence_key(row: dict[str, Any], fallback: int) -> str:
    evidence = row.get("simulation_evidence")
    if isinstance(evidence, dict) and evidence.get("correlation_id"):
        return f"correlation:{evidence['correlation_id']}"
    return f"ordinal:{fallback}"


def _case_metadata(row: dict[str, Any]) -> dict[str, Any]:
    native_case = row.get("native_case")
    metadata = {"name": str(row.get("case_name", ""))}
    if isinstance(native_case, dict) and native_case.get("id") is not None:
        metadata["id"] = str(native_case["id"])
    return metadata


def _new_evaluator(
    ordinal: int, row: dict[str, Any], matrix: list[dict[str, Any]],
) -> dict[str, Any]:
    evaluator = {
        "evaluator_key": f"evaluator-{ordinal}",
        "metadata": {
            "name": str(row.get("evaluator", "")),
            "type": str(row.get("evaluator_type", "")),
        },
        "results": [],
    }
    matrix.append(evaluator)
    return evaluator


def _append_evidence(
    artifacts: dict[str, Any], case_key: str, row: dict[str, Any], ordinal: int,
) -> tuple[str | None, str | None]:
    evidence = row.get("simulation_evidence")
    if not isinstance(evidence, dict):
        return None, None
    correlation_id = evidence.get("correlation_id")
    metadata = {"correlation_id": correlation_id} if correlation_id else {}
    target_key = f"target-session-{ordinal}"
    actor_key = f"actor-evidence-{ordinal}"
    artifacts["target_sessions"].append({
        "target_session_key": target_key,
        "case_key": case_key,
        "metadata": metadata,
        "target_session": evidence.get("target_session"),
        "target_span_snapshot": evidence.get("target_span_snapshot", []),
    })
    artifacts["actor_evidence"].append({
        "actor_evidence_key": actor_key,
        "case_key": case_key,
        "metadata": metadata,
        "actor_turns": evidence.get("actor_turns", []),
    })
    return target_key, actor_key


def build_run_artifacts(report: ExperimentReport) -> dict[str, Any]:
    """Build schema-v1 artifacts using ordinal keys rather than display names."""
    summary = report.summary
    artifacts: dict[str, Any] = {
        "schema_version": ARTIFACTS_SCHEMA_VERSION,
        "aggregate": {
            "name": str(summary.get("aggregate_strategy", "unspecified")),
            "metrics": {
                key: summary.get(key)
                for key in ("overall_score", "pass_rate", "total_cases")
            },
        },
        "evaluator_matrix": [],
        "native_reports": [],
        "case_manifests": [],
        "target_sessions": [],
        "actor_evidence": [],
    }
    cases: dict[str, dict[str, Any]] = {}
    evaluator_by_ordinal: dict[int, dict[str, Any]] = {}
    previous_signature: tuple[str, str] | None = None
    fallback_ordinal = -1
    evidence_case_keys: dict[str, str] = {}

    for result_ordinal, row in enumerate(report.case_results):
        signature = (str(row.get("evaluator", "")), str(row.get("evaluator_type", "")))
        ordinal = row.get("evaluator_ordinal")
        if not isinstance(ordinal, int):
            if signature != previous_signature:
                fallback_ordinal += 1
                previous_signature = signature
            ordinal = fallback_ordinal
        evaluator = evaluator_by_ordinal.get(ordinal)
        if evaluator is None:
            evaluator = _new_evaluator(ordinal, row, artifacts["evaluator_matrix"])
            evaluator_by_ordinal[ordinal] = evaluator
        evidence_key = _evidence_key(row, len(evaluator["results"]))
        case_key = evidence_case_keys.setdefault(evidence_key, f"case-{len(evidence_case_keys)}")
        manifest = cases.get(case_key)
        if manifest is None:
            manifest = {
                "case_key": case_key,
                "case_ordinal": len(cases),
                "metadata": _case_metadata(row),
                "result_keys": [],
            }
            target_key, actor_key = _append_evidence(artifacts, case_key, row, len(cases))
            if target_key:
                manifest["target_session_key"] = target_key
                manifest["actor_evidence_key"] = actor_key
            artifacts["case_manifests"].append(manifest)
            cases[case_key] = manifest
        result_key = f"result-{result_ordinal}"
        evaluator["results"].append({
            "result_key": result_key,
            "case_key": case_key,
            "score": row.get("score", 0.0),
            "passed": bool(row.get("passed", False)),
            "reason": row.get("reason", ""),
        })
        manifest["result_keys"].append(result_key)

    evaluator_keys = [item["evaluator_key"] for item in artifacts["evaluator_matrix"]]
    evaluator_keys_by_ordinal = {
        ordinal: evaluator["evaluator_key"] for ordinal, evaluator in evaluator_by_ordinal.items()
    }
    native_reports = summary.get("native_reports", [])
    for ordinal, native_report in enumerate(native_reports):
        report_keys = evaluator_keys if len(native_reports) == 1 else (
            [evaluator_keys_by_ordinal[ordinal]] if ordinal in evaluator_keys_by_ordinal else []
        )
        artifacts["native_reports"].append({
            "native_report_key": f"native-report-{ordinal}",
            "evaluator_keys": report_keys,
            "report": native_report,
        })
    return artifacts
