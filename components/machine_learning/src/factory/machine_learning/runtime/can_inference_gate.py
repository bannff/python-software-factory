"""Truthful aggregate deployability gate for requested CAN classifiers."""
from __future__ import annotations

from typing import Any


def build_inference_gate(
    table: list[dict[str, Any]], warm_model_ids: list[str],
) -> dict[str, Any]:
    """Treat only an exact promotable, passed passport as deployable."""
    failures = [row for row in table if not _is_promotable(row)]
    if table and not failures:
        model_ids = [str(row["model_id"]) for row in table if row.get("model_id")]
        return {
            "status": "passed", "failed_model_types": [],
            "promotable_model_ids": model_ids, "warm_model_ids": warm_model_ids,
            "live_model_ids": [],
        }
    failed_types = sorted({str(row.get("model_type", "unknown")) for row in failures})
    codes = {str(row.get("error_code")) for row in failures if row.get("error_code")}
    if "inference_adapter_defect" in codes:
        error_code = "inference_adapter_defect"
    elif "training_failed" in codes:
        error_code = "training_failed"
    elif "passport_publication_failed" in codes:
        error_code = "passport_publication_failed"
    else:
        error_code = "passport_not_promotable"
    return {
        "status": "failed", "error_code": error_code,
        "failed_model_types": failed_types, "promotable_model_ids": [],
        "warm_model_ids": warm_model_ids, "live_model_ids": [],
    }


def _is_promotable(row: dict[str, Any]) -> bool:
    return bool(
        row.get("passport_ref")
        and row.get("passport_digest")
        and row.get("promotion_status") == "promotable"
        and row.get("conformance_status") == "passed"
    )


__all__ = ["build_inference_gate"]
