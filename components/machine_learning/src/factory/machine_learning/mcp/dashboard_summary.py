"""Aggregate dashboard tools for real model-training runs."""
from __future__ import annotations

from typing import Any
from factory.mcp_utils.interface import ToolResult, deterministic, fail
from .dashboard_summary_dtos import (DashboardSummaryOutput, EmptyInput,
    RunIdInput, RunRegressionOutput, TrainingRunOutput, TrainingRunsOutput)


def register(mcp: Any) -> None:
    """Register training-run dashboard tools."""

    @mcp.tool()
    @deterministic(input_model=EmptyInput, output_model=TrainingRunsOutput)
    def ml_list_training_runs() -> ToolResult[TrainingRunsOutput]:
        """List persisted model-training runs, newest first."""
        try:
            from ..runtime.adapters.training_run_reader import list_training_runs
            runs = list_training_runs()
            return TrainingRunsOutput(runs=runs, count=len(runs))
        except Exception as exc:
            return fail(str(exc))

    @mcp.tool()
    @deterministic(input_model=RunIdInput, output_model=TrainingRunOutput)
    def ml_get_training_run(run_id: str) -> ToolResult[TrainingRunOutput]:
        """Return the full persisted record for one training run."""
        try:
            from ..runtime.adapters.training_run_reader import get_training_run
            return TrainingRunOutput(found=(record := get_training_run(run_id)) is not None, run=record)
        except Exception as exc:
            return fail(str(exc))

    @mcp.tool()
    @deterministic(input_model=RunIdInput, output_model=RunRegressionOutput)
    def ml_get_run_regression(run_id: str) -> ToolResult[RunRegressionOutput]:
        """Return the regression signal for a training run vs its predecessor."""
        try:
            from ..runtime.adapters.training_run_reader import list_training_runs
            run = next((item for item in list_training_runs() if item.get("run_id") == run_id), None)
            if run is None:
                return RunRegressionOutput(found=False)
            return RunRegressionOutput(found=True, regressed=run.get("regression_state") == "regressed", regression_state=run.get("regression_state", "baseline"), metric=run.get("primary_metric", ""), metric_delta=run.get("metric_delta", 0.0), previous_run_id=run.get("previous_run_id"))
        except Exception as exc:
            return fail(str(exc))

    @mcp.tool()
    @deterministic(input_model=EmptyInput, output_model=DashboardSummaryOutput)
    def ml_get_dashboard_summary() -> ToolResult[DashboardSummaryOutput]:
        """Return aggregate dashboard data for the ML models view."""
        try:
            from ..runtime.adapters.training_run_reader import list_training_runs
            return DashboardSummaryOutput(**_build_dashboard_summary(list_training_runs()))
        except Exception as exc:
            return fail(str(exc))


def _build_dashboard_summary(runs: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate training runs into dashboard-friendly structures."""
    latest_by_experiment: dict[str, dict[str, Any]] = {}
    histories: dict[str, list[dict[str, Any]]] = {}
    for run in runs:
        name = str(run.get("experiment_name", ""))
        histories.setdefault(name, []).append(run)
        latest_by_experiment.setdefault(name, run)
    experiments = []
    for name, latest in latest_by_experiment.items():
        history = histories.get(name, [])
        values = [float(item.get("primary_value", 0.0)) for item in history]
        experiments.append({"experiment_name": name, "runs": len(history), "latest_run_id": latest.get("run_id", ""), "latest_timestamp": latest.get("timestamp", ""), "latest_model_type": latest.get("model_type", ""), "model_types": sorted({str(item.get("model_type", "")) for item in history}), "primary_metric": latest.get("primary_metric", ""), "latest_value": latest.get("primary_value", 0.0), "metric_delta": latest.get("metric_delta", 0.0), "avg_value": round(sum(values) / len(values), 3) if values else 0.0, "best_value": max(values) if values else 0.0, "trend_direction": latest.get("trend_direction", "flat"), "regression_state": latest.get("regression_state", "baseline"), "recent_values": [item.get("primary_value", 0.0) for item in reversed(history[:8])], "source": latest.get("source", "mcp")})
    experiments.sort(key=lambda item: item.get("latest_timestamp", ""), reverse=True)
    experiments.sort(key=lambda item: item.get("regression_state") != "regressed")
    series = [{"label": str(run.get("experiment_name", "run"))[:18], "value": run.get("primary_value", 0.0), "model_type": run.get("model_type", ""), "timestamp": run.get("timestamp", "")} for run in reversed(runs[:10])]
    values = [float(run.get("primary_value", 0.0)) for run in runs]
    return {"overview": {"runs": len(runs), "experiments": len(experiments), "model_types": len({str(run.get("model_type", "")) for run in runs}), "regressions": sum(1 for item in experiments if item.get("regression_state") == "regressed"), "avg_metric": round(sum(values) / len(values), 3) if values else 0.0}, "series": series, "experiments": experiments}


__all__ = ["register"]
