"""Backward-compatible GT score projection through the canonical Evals writer."""
from __future__ import annotations

import logging
from typing import Any, Callable

from .run_record_contract import utc_timestamp

logger = logging.getLogger(__name__)


def persist_score_result(
    invoker: Callable[..., Any], run_id: str, workflow_type: str, target_app: str,
    vuln_class: str, scoring: dict[str, Any], domain_class: str = "",
    source: str = "experiment",
) -> bool:
    """Persist a score-only projection without replacing a full run artifact."""
    if not run_id:
        return False
    projection = {
        "workflow_type": workflow_type, "target_app": target_app,
        "vuln_class": vuln_class, "domain_class": domain_class,
        "precision": scoring.get("precision", 0), "recall": scoring.get("recall", 0),
        "f1": scoring.get("f1", 0), "true_positives": scoring.get("true_positives", 0),
        "false_positives": scoring.get("false_positives_count", 0),
        "false_negatives": scoring.get("false_negatives", 0),
        "matched_count": len(scoring.get("matched", []) or []),
        "missed_count": len(scoring.get("missed", []) or []),
    }
    try:
        persisted_at = utc_timestamp()
        result = invoker(
            "evals_record_run", run_id=run_id,
            experiment_name=f"score:{workflow_type}:{target_app}", verdict="SCORED",
            pass_rate=float(projection["f1"] or 0), avg_score=float(projection["f1"] or 0),
            total_cases=projection["matched_count"] + projection["missed_count"],
            passed=projection["true_positives"], source=source,
            timestamp=persisted_at,
            record_kind="evaluation_score_projection", terminal_state="scored",
            score_projection=projection,
        )
        from factory.mcp_utils.interface import ToolResult
        envelope = result if isinstance(result, ToolResult) else ToolResult.model_validate(result)
        if not envelope.ok or envelope.data is None:
            return False
        data = envelope.data.model_dump() if hasattr(envelope.data, "model_dump") else envelope.data
    except Exception as exc:
        logger.warning("score persistence failed for run=%s: %s", run_id, exc)
        return False
    if isinstance(data, dict) and data.get("persisted"):
        from .trajectory_writer import best_effort_record, default_landing_root
        best_effort_record(
            default_landing_root(), data.get("pointer"),
            run_id=run_id, recorded_at=persisted_at, verdict="scored",
        )
    return bool(data.get("persisted")) if isinstance(data, dict) else False
