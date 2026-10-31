"""Honest population and progress projection for the ML Observatory."""
from __future__ import annotations

from typing import Any

_PRIMARY = ("auroc", "f1", "accuracy")
_EPSILON = 0.01


def _source(sources: list[dict[str, Any]], name: str) -> dict[str, Any]:
    return next((item for item in sources if item.get("name") == name), {"value": None})


def _primary(metrics: dict[str, Any]) -> tuple[str, float]:
    for key in (*_PRIMARY, *metrics.keys()):
        value = metrics.get(key)
        if isinstance(value, (int, float)):
            return key, round(float(value), 3)
    return "", 0.0


def enrich_receipts(receipts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Add stable trend fields while retaining all source-native fields."""
    ordered = sorted(receipts, key=lambda row: str(row.get("timestamp", "")))
    previous: dict[str, dict[str, Any]] = {}
    enriched: list[dict[str, Any]] = []
    for receipt in ordered:
        row = dict(receipt)
        experiment = str(row.get("experiment_name", ""))
        metric, value = _primary(row.get("metrics", {}))
        prior = previous.get(experiment)
        delta, direction, state = 0.0, "flat", "baseline"
        if prior is not None:
            delta = round(value - float(prior["primary_value"]), 3)
            if delta > _EPSILON:
                direction, state = "up", "improved"
            elif delta < -_EPSILON:
                direction, state = "down", "regressed"
            else:
                state = "steady"
        row.update(
            primary_metric=metric, primary_value=value,
            previous_run_id=prior.get("run_id") if prior else None,
            metric_delta=delta, trend_direction=direction,
            regression_state=state,
        )
        enriched.append(row)
        previous[experiment] = row
    return list(reversed(enriched))


def _experiments(runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for run in runs:
        grouped.setdefault(str(run.get("experiment_name", "")), []).append(run)
    rows: list[dict[str, Any]] = []
    for name, history in grouped.items():
        latest = history[0]
        values = [float(item.get("primary_value", 0.0)) for item in history]
        rows.append({
            "experiment_name": name, "runs": len(history),
            "latest_run_id": latest.get("run_id"),
            "latest_timestamp": latest.get("timestamp", ""),
            "latest_model_type": latest.get("model_type", ""),
            "model_types": sorted({str(item.get("model_type", "")) for item in history}),
            "primary_metric": latest.get("primary_metric", ""),
            "latest_value": latest.get("primary_value", 0.0),
            "metric_delta": latest.get("metric_delta", 0.0),
            "avg_value": round(sum(values) / len(values), 3),
            "best_value": max(values),
            "trend_direction": latest.get("trend_direction", "flat"),
            "regression_state": latest.get("regression_state", "baseline"),
            "recent_values": [item.get("primary_value", 0.0) for item in reversed(history[:8])],
            "source": latest.get("source", "mcp"),
        })
    rows.sort(key=lambda row: (row["regression_state"] != "regressed", -len(row["recent_values"]), row["experiment_name"]))
    return rows


def _refs(run: dict[str, Any], plural: str, singular: str) -> list[str]:
    value = run.get(plural)
    if isinstance(value, list):
        return [str(item) for item in value if item]
    value = run.get(singular)
    return [str(value)] if value else []


def _models(runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    models: list[dict[str, Any]] = []
    seen: set[str] = set()
    for run in runs:
        uri = str(run.get("model_path", ""))
        if not uri or uri in seen:
            continue
        seen.add(uri)
        models.append({
            "row_id": f"receipt-model:{run.get('run_id')}", "entity_id": None,
            "source": "training_receipt", "source_run_id": run.get("run_id"),
            "artifact_uri": uri, "model_type": run.get("model_type", ""),
            "dataset_refs": _refs(run, "dataset_refs", "dataset_id"),
            "evaluation_refs": _refs(run, "evaluation_refs", "evaluation_id"),
            "provenance_state": "partial",
        })
    return models


def _state(training: list[Any] | None, learning: list[Any] | None) -> tuple[str | None, str]:
    if training is None and learning is None:
        return None, "Training receipts and learning activity are unavailable."
    if training is None:
        return None, "Learning activity is available; training receipts are unavailable."
    if learning is None:
        return None, "Training receipts are available; learning activity is unavailable."
    if training and learning:
        return "mixed", "Training and learning activity are both available."
    if training:
        return "training_only", "Training receipts exist; no learning runs."
    if learning:
        return "learning_only", "Learning loop active; no persisted training receipts yet."
    return "empty", "No persisted training or learning runs."


def _attention(runs: list[dict[str, Any]], learning: list[dict[str, Any]]) -> list[dict[str, Any]]:
    items = [
        {"id": f"regression:{r.get('run_id')}", "kind": "regression", "title": r.get("experiment_name"), "run_id": r.get("run_id")}
        for r in runs if r.get("regression_state") == "regressed"
    ]
    items += [
        {"id": f"training:{r.get('run_id')}", "kind": "failure", "title": r.get("experiment_name"), "run_id": r.get("run_id")}
        for r in runs if r.get("status") == "failed"
    ]
    items += [
        {"id": f"provenance:{r.get('run_id')}", "kind": "incomplete_provenance", "title": r.get("experiment_name"), "run_id": r.get("run_id")}
        for r in runs if not r.get("model_path")
    ]
    items += [
        {"id": f"learning:{r.get('workflow_run_id') or r.get('run_id')}", "kind": "failure", "title": r.get("display_title"), "run_id": r.get("run_id")}
        for r in learning if r.get("status") == "failed"
    ]
    return items[:20]


def build_summary(sources: list[dict[str, Any]]) -> dict[str, Any]:
    """Build the complete availability-aware Observatory summary."""
    training_value = _source(sources, "training_receipts").get("value")
    learning = _source(sources, "learning_runs").get("value")
    fine_jobs = _source(sources, "fine_tuning_jobs").get("value")
    runs = enrich_receipts(training_value or [])
    experiments = _experiments(runs)
    models = _models(runs)
    state, message = _state(training_value, learning)
    healths = [source.get("health") for source in sources]
    health = "error" if all(value == "error" for value in healths) else (
        "degraded" if any(value != "healthy" for value in healths) else "healthy"
    )
    series = [{"label": str(r.get("experiment_name") or r.get("run_id"))[:18], "value": r.get("primary_value", 0), "timestamp": r.get("timestamp", "")} for r in reversed(runs[:10])]
    if not series and learning:
        series = [{"label": str(r.get("display_title") or r.get("run_id"))[:18], "value": r.get("score"), "timestamp": r.get("updated_at", "")} for r in reversed(learning[:10]) if isinstance(r.get("score"), (int, float))]
    return {
        "population_state": state, "health": health, "message": message,
        "sources": [{k: v for k, v in source.items() if k != "value"} for source in sources],
        "overview": {
            "training_runs": len(runs) if training_value is not None else None,
            "experiments": len(experiments) if training_value is not None else None,
            "receipt_models": len(models) if training_value is not None else None,
            "fine_tuning_jobs": len(fine_jobs) if fine_jobs is not None else None,
            "live_models": None,
            "regressions": sum(row["regression_state"] == "regressed" for row in experiments) if training_value is not None else None,
            "learning_runs": len(learning) if learning is not None else None,
        },
        "series": series, "attention": _attention(runs, learning or []),
        "training_runs": runs, "experiments": experiments, "models": models,
        "fine_tuning_jobs": fine_jobs or [], "learning_runs": learning or [],
    }


__all__ = ["build_summary", "enrich_receipts"]
