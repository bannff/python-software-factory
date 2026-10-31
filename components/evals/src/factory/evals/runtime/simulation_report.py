"""Convert Strands Evals reports into the Evals simulation report contract."""
from __future__ import annotations

from typing import Any

from .ports import ExperimentConfig, ExperimentReport


def _jsonable(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return _jsonable(value.model_dump(mode="json"))
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value if value is None or isinstance(value, (bool, int, float, str)) else str(value)


def build_report(
    config: ExperimentConfig, reports: Any, evidence_by_execution: list[dict[str, Any]] | None = None,
) -> ExperimentReport:
    """Retain every evaluator row, native report, and target-only evidence."""
    from strands_evals.types.evaluation_report import EvaluationReport
    per_evaluator_reports = isinstance(reports, list)
    raw_reports = reports if per_evaluator_reports else [reports]
    aggregate = EvaluationReport.flatten(raw_reports) if per_evaluator_reports and reports else reports
    evidence = evidence_by_execution or []
    if per_evaluator_reports:
        evidence_rows = [item for report in raw_reports for item in evidence[:len(getattr(report, "cases", []))]]
        evaluator_ordinals = [
            ordinal for ordinal, report in enumerate(raw_reports)
            for _ in range(len(getattr(report, "cases", [])))
        ]
    else:
        count = len(getattr(aggregate, "cases", []))
        evidence_rows = [evidence[index % len(evidence)] for index in range(count)] if evidence else []
        case_count = len(config.cases)
        evaluator_ordinals = [index // case_count if case_count else index for index in range(count)]
    rows: list[dict[str, Any]] = []
    for index, native_case in enumerate(getattr(aggregate, "cases", [])):
        case = dict(native_case)
        row = {
            "case_name": str(case.get("name", f"case-{index}")),
            "evaluator": case.get("evaluator", ""),
            "evaluator_ordinal": evaluator_ordinals[index] if index < len(evaluator_ordinals) else index,
            "evaluator_type": case.get("evaluator_type", ""),
            "score": getattr(aggregate, "scores", [])[index] if index < len(getattr(aggregate, "scores", [])) else 0.0,
            "passed": getattr(aggregate, "test_passes", [])[index] if index < len(getattr(aggregate, "test_passes", [])) else False,
            "reason": getattr(aggregate, "reasons", [])[index] if index < len(getattr(aggregate, "reasons", [])) else "",
            "native_case": _jsonable(case),
            "detailed_results": _jsonable(getattr(aggregate, "detailed_results", [])[index]) if index < len(getattr(aggregate, "detailed_results", [])) else [],
            "diagnosis": _jsonable(getattr(aggregate, "diagnoses", [])[index]) if index < len(getattr(aggregate, "diagnoses", [])) else None,
            "recommendation": _jsonable(getattr(aggregate, "recommendations", [])[index]) if index < len(getattr(aggregate, "recommendations", [])) else None,
        }
        if index < len(evidence_rows):
            row["simulation_evidence"] = evidence_rows[index]
        rows.append(row)
    passes = getattr(aggregate, "test_passes", [])
    summary = {
        "overall_score": getattr(aggregate, "overall_score", 0.0),
        "pass_rate": sum(passes) / len(passes) if passes else 0.0,
        "total_cases": len(rows),
        "simulation": True,
        "aggregate_strategy": "sdk_evaluation_report_flatten" if per_evaluator_reports else "sdk_run_evaluations_flatten",
        "native_reports": [report.to_dict() for report in raw_reports if report is not None],
    }
    return ExperimentReport(
        experiment_name=config.name or "simulation", case_results=rows,
        summary=summary, evaluator_names=config.evaluator_names,
    )
