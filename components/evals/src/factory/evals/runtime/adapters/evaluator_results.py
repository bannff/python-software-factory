"""Shared fail-closed aggregation for manually invoked evaluators."""
from __future__ import annotations

import logging
from typing import Any

AGGREGATION_POLICY = "all_requested"


def json_safe_details(outputs: list[Any]) -> list[Any]:
    """Preserve every SDK output as JSON-safe durable detail."""
    return [_json_safe(output) for output in outputs]


def run_evaluators(
    evaluators: list[Any], names: list[str], eval_data: Any, logger: logging.Logger,
) -> list[dict[str, Any]]:
    """Run each evaluator and aggregate its outputs on the rail (no SDK hook).

    The rail owns aggregation so any provider's neutral evaluator only needs
    ``evaluate(data) -> [EvaluationOutput]``. Evaluator errors remain scored
    rows labelled ``error`` (fail-closed).
    """
    rows = []
    for evaluator, name in zip(evaluators, names, strict=True):
        try:
            outputs = evaluator.evaluate(eval_data)
            rows.append({
                "evaluator": name,
                **_aggregate_outputs(outputs),
                "detailed_results": json_safe_details(outputs),
            })
        except Exception as exc:  # noqa: BLE001 — failures are scored evidence
            logger.warning("Evaluator %s failed: %s", name, exc)
            rows.append(_failed_row(name, str(exc), "error"))
    return rows


def _aggregate_outputs(outputs: list[Any]) -> dict[str, Any]:
    """Compute score/test_pass/reason/label over one evaluator's outputs."""
    if not outputs:
        return {"score": 0.0, "test_pass": False, "reason": "No evaluation outputs produced", "label": ""}
    return {
        "score": sum(float(item.score) for item in outputs) / len(outputs),
        "test_pass": all(bool(item.test_pass) for item in outputs),
        "reason": " | ".join(str(item.reason or "") for item in outputs),
        "label": _single_label(outputs),
    }


def aggregate_rows(
    rows: list[dict[str, Any]], **summary_fields: Any,
) -> dict[str, Any]:
    """Aggregate over all requested rows, including evaluator errors."""
    total = len(rows)
    return {
        "results": rows,
        "summary": {
            "avg_score": (
                sum(float(row.get("score", 0.0)) for row in rows) / total
                if total else 0.0
            ),
            "pass_rate": (
                sum(bool(row.get("test_pass")) for row in rows) / total
                if total else 0.0
            ),
            "total_evaluators": total,
            "error_count": sum(row.get("label") == "error" for row in rows),
            "aggregation_policy": AGGREGATION_POLICY,
            **summary_fields,
        },
    }


def _single_label(outputs: list[Any]) -> str:
    if len(outputs) != 1:
        return ""
    only, = outputs
    return str(getattr(only, "label", "") or "")


def _json_safe(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if hasattr(value, "__dict__"):
        return _json_safe(vars(value))
    return str(value)


def _failed_row(name: str, reason: str, label: str) -> dict[str, Any]:
    return {
        "evaluator": name,
        "score": 0.0,
        "test_pass": False,
        "reason": reason,
        "label": label,
        "detailed_results": [],
    }
