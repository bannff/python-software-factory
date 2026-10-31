"""Deterministic MCP tools for machine_learning — contract + tracking."""
from __future__ import annotations

from typing import Callable

from typing import Any
from factory.mcp_utils.interface import ToolResult, deterministic, fail, ok

from ..runtime.learning_projection import _find_learning_run, _load_learning_runs, _timeline_line
from ..runtime.runtime import TrackingRuntime
from .deterministic_dtos import (
    CapabilitiesOutput, ConfigSchemaOutput, EmptyInput, ExperimentIdInput,
    ExperimentOutput, ExperimentsOutput, HealthOutput, LearningArtifactsOutput,
    LearningRunOutput, LearningRunsOutput, LearningSummaryOutput,
    LearningTimelineOutput, LearningRunsInput, LearningSummaryInput,
    ExperimentListInput, RunIdInput, TrackingRunOutput,
)


def register(mcp: Any, get_runtime: Callable[[], TrackingRuntime]) -> None:
    """Register contract and tracking deterministic tools."""

    @mcp.tool(name="ml_get_capabilities")
    @deterministic(input_model=EmptyInput, output_model=CapabilitiesOutput)
    def ml_get_capabilities() -> ToolResult[CapabilitiesOutput]:
        """Return machine-readable capabilities for machine_learning brick."""
        return CapabilitiesOutput(name="machine_learning", version="2.0.0",
            backends=TrackingRuntime.available_backends(),
            finetuning_backends=TrackingRuntime.available_finetuning_backends(),
            features=["experiments", "runs", "metrics", "params", "artifacts",
                "finetuning", "lora", "qlora", "model_export",
                "training_objectives", "checkpoint_lifecycle"])

    @mcp.tool(name="ml_health_check")
    @deterministic(input_model=EmptyInput, output_model=HealthOutput)
    def ml_health_check() -> ToolResult[HealthOutput]:
        """Fast readiness probe for machine_learning brick."""
        try:
            health = get_runtime().health_check()
            return HealthOutput(healthy=all(h.healthy for h in health.values()) if health else True,
                trackers={key: {"healthy": value.healthy, "backend": value.backend}
                          for key, value in health.items()})
        except Exception as exc:
            return fail(str(exc))

    @mcp.tool(name="ml_describe_config_schema")
    @deterministic(input_model=EmptyInput, output_model=ConfigSchemaOutput)
    def ml_describe_config_schema() -> ToolResult[ConfigSchemaOutput]:
        """Describe machine_learning configuration schema."""
        return ConfigSchemaOutput(type="object", properties={"backend": {
            "type": "string", "enum": ["memory", "mlflow", "tensorboard"],
            "description": "Tracking backend. Default resolves from ML_TRACKER_BACKEND env (fallback memory).", "default": "memory"},
            "finetuning_backend": {"type": "string",
            "enum": TrackingRuntime.available_finetuning_backends(),
            "description": "Fine-tuning backend", "default": "memory"}})

    @mcp.tool()
    @deterministic(input_model=ExperimentIdInput, output_model=ExperimentOutput)
    def tracking_get_experiment(experiment_id: str) -> ToolResult[ExperimentOutput]:
        """Get an experiment by ID."""
        try:
            exp = get_runtime().get_tracker().get_experiment(experiment_id)
            return ExperimentOutput(found=bool(exp), id=exp.id if exp else None,
                name=exp.name if exp else None)
        except Exception as exc:
            return fail(str(exc))

    @mcp.tool()
    @deterministic(input_model=ExperimentListInput, output_model=ExperimentsOutput)
    def tracking_list_experiments(limit: int = 100) -> ToolResult[ExperimentsOutput]:
        """List all experiments."""
        try:
            exps = get_runtime().get_tracker().list_experiments()[:limit]
            return ExperimentsOutput(experiments=[{"id": e.id, "name": e.name} for e in exps],
                count=len(exps))
        except Exception as exc:
            return fail(str(exc))

    @mcp.tool()
    @deterministic(input_model=RunIdInput, output_model=TrackingRunOutput)
    def tracking_get_run(run_id: str) -> ToolResult[TrackingRunOutput]:
        """Get a run by ID."""
        try:
            run = get_runtime().get_tracker().get_run(run_id)
            return TrackingRunOutput(found=bool(run), id=run.id if run else None,
                experiment_id=run.experiment_id if run else None, name=run.name if run else None,
                status=run.status if run else None, params=run.params if run else None,
                metrics=run.metrics if run else None)
        except Exception as exc:
            return fail(str(exc))

    @mcp.tool()
    @deterministic(input_model=LearningRunsInput, output_model=LearningRunsOutput)
    def ml_list_learning_runs(limit: int = 50) -> ToolResult[LearningRunsOutput]:
        """List learning-loop runs projected from canonical runtime events."""
        try:
            runs = _load_learning_runs(limit=limit)
            return LearningRunsOutput(learning_runs=runs, count=len(runs))
        except Exception as exc:
            return fail(str(exc))

    @mcp.tool()
    @deterministic(input_model=RunIdInput, output_model=LearningRunOutput)
    def ml_get_learning_run(run_id: str) -> ToolResult[LearningRunOutput]:
        """Get a single learning-loop run projection with event history."""
        try:
            run = next((item for item in _load_learning_runs(limit=200)
                if item.get("run_id") == run_id or item.get("workflow_run_id") == run_id), None)
            return LearningRunOutput(found=run is not None, run=run)
        except Exception as exc:
            return fail(str(exc))

    @mcp.tool()
    @deterministic(input_model=LearningSummaryInput, output_model=LearningSummaryOutput)
    def ml_get_learning_summary(limit: int = 200) -> ToolResult[LearningSummaryOutput]:
        """Summarize the current learning-loop portfolio."""
        try:
            runs = _load_learning_runs(limit=limit)
            scores = [run["score"] for run in runs if isinstance(run.get("score"), (int, float))]
            rewards = [run["reward_value"] for run in runs if isinstance(run.get("reward_value"), (int, float))]
            return LearningSummaryOutput(total_runs=len(runs), completed_runs=sum(1 for r in runs if r.get("graph_completed_event_id")), rewarded_runs=sum(1 for r in runs if r.get("wallet_rewarded")), memory_backed_runs=sum(1 for r in runs if r.get("memory_stored")), converged_runs=sum(1 for r in runs if r.get("converged") is True), average_score=round(sum(scores) / len(scores), 3) if scores else 0.0, total_reward_value=round(sum(rewards), 2) if rewards else 0.0, latest_updated_at=max((r.get("updated_at", "") for r in runs), default=""))
        except Exception as exc:
            return fail(str(exc))

    @mcp.tool()
    @deterministic(input_model=RunIdInput, output_model=LearningTimelineOutput)
    def ml_get_learning_run_timeline(run_id: str) -> ToolResult[LearningTimelineOutput]:
        """Return a human-readable timeline for one learning-loop run."""
        try:
            run = _find_learning_run(run_id)
            events = [] if run is None else [_timeline_line(event, run) for event in run.get("event_history", [])]
            return LearningTimelineOutput(found=run is not None, events=events, count=len(events))
        except Exception as exc:
            return fail(str(exc))

    @mcp.tool()
    @deterministic(input_model=RunIdInput, output_model=LearningArtifactsOutput)
    def ml_get_learning_run_artifacts(run_id: str) -> ToolResult[LearningArtifactsOutput]:
        """Return the materialized artifacts for one learning-loop run."""
        try:
            run = _find_learning_run(run_id)
            if run is None:
                return LearningArtifactsOutput(found=False)
            artifacts = [text for present, text in [
                (run.get("reward_event_id"), f"Reward computed: {run.get('reward_value', 0)} {run.get('reward_unit', 'tokens')}"),
                (run.get("wallet_id"), f"Wallet credited: {run.get('wallet_id')} ({run.get('transaction_id', 'pending tx')})"),
                (run.get("memory_id"), f"Learning persisted: {run.get('memory_id')} ({run.get('summary_type', 'summary')})"),
                (run.get("metric_id"), f"Convergence metric recorded: {run.get('metric_id')}")]
                if present]
            return LearningArtifactsOutput(found=True, artifacts=artifacts, count=len(artifacts))
        except Exception as exc:
            return fail(str(exc))
