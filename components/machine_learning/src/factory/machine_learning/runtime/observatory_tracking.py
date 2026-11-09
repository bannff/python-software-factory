"""Tracker-backed experiments for the ML Observatory.

The tracking tools (``tracking_create_experiment`` / ``tracking_start_run``) own
a second store next to training receipts. Reading it here keeps the
Experiments tab a projection of every experiment the platform knows about,
whichever tool created it.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable

SOURCE_NAME = "tracked_experiments"


def _iso(value: Any) -> str:
    return value.isoformat() if isinstance(value, datetime) else str(value or "")


def _primary(metrics: dict[str, float]) -> tuple[str, float]:
    for key in ("auroc", "f1", "accuracy", *metrics):
        value = metrics.get(key)
        if isinstance(value, (int, float)):
            return key, round(float(value), 3)
    return "", 0.0


def load_tracked_experiments(runtime_supplier: Callable[[], Any]) -> dict[str, Any]:
    """Read tracker experiments and their runs inside one exception boundary."""
    try:
        tracker = runtime_supplier().get_tracker()
        runs = tracker.list_runs()
        rows = [
            {"id": exp.id, "name": exp.name, "description": exp.description,
             "created_at": _iso(exp.created_at),
             "runs": [r for r in runs if r.experiment_id == exp.id]}
            for exp in tracker.list_experiments()
        ]
        health, error = "healthy", None
        value: Any = rows
    except Exception as exc:
        health, error, value = "error", str(exc), None
    return {
        "name": SOURCE_NAME, "health": health, "durability": "runtime",
        "freshness": datetime.now(timezone.utc).isoformat(),
        "value": value, "error": error,
    }


def tracked_experiment_rows(experiments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Shape tracker experiments like receipt-derived experiment rows."""
    rows: list[dict[str, Any]] = []
    for exp in experiments:
        runs = sorted(exp["runs"], key=lambda r: _iso(r.started_at), reverse=True)
        latest = runs[0] if runs else None
        metric, value = _primary(latest.metrics) if latest else ("", 0.0)
        values = [_primary(r.metrics)[1] for r in runs]
        rows.append({
            "experiment_name": exp["name"], "experiment_id": exp["id"],
            "description": exp["description"], "runs": len(runs),
            "latest_run_id": latest.id if latest else None,
            "latest_timestamp": _iso(latest.started_at) if latest else exp["created_at"],
            "latest_status": latest.status if latest else "no_runs",
            "latest_model_type": "", "model_types": [],
            "primary_metric": metric, "latest_value": value, "metric_delta": 0.0,
            "avg_value": round(sum(values) / len(values), 3) if values else 0.0,
            "best_value": max(values) if values else 0.0,
            "trend_direction": "flat", "regression_state": "baseline",
            "recent_values": list(reversed(values[:8])), "source": "tracking",
        })
    return rows


__all__ = ["SOURCE_NAME", "load_tracked_experiments", "tracked_experiment_rows"]
