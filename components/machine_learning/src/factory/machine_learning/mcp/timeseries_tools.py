"""Typed MCP tools for time-series training and generation."""
from __future__ import annotations

from typing import Any, Callable

from factory.mcp_utils.interface import deterministic, fail, ok, operational
from factory.mcp_utils.runtime.tool_result import ToolResult

from ..runtime.adapters.timeseries_training import MemoryTimeSeriesTrainingAdapter
from ..runtime.adapters.training_run_store import persist_training_run
from ..runtime.emit import emit_ml_event
from ..runtime.runtime import TrackingRuntime
from ..runtime.time_series_ports import (
    TimeSeriesModelConfig, TimeSeriesModelType, TimeSeriesTrainingConfig,
    validate_model_config_for_family,
)
from .timeseries_pipeline_models import (
    CompareTimeSeriesInput, CompareTimeSeriesOutput, ContinueTimeSeriesInput,
    ContinueTimeSeriesOutput, ListTimeSeriesModelsInput, ListTimeSeriesModelsOutput,
    PredictTimeSeriesInput, PredictTimeSeriesOutput, SampleTimeSeriesInput,
    SampleTimeSeriesOutput, TrainTimeSeriesInput, TrainTimeSeriesOutput,
)


def register(mcp: Any, get_runtime: Callable[[], TrackingRuntime]) -> None:
    """Register time-series training tools."""

    @mcp.tool()
    @operational(input_model=TrainTimeSeriesInput, output_model=TrainTimeSeriesOutput)
    def ml_train_timeseries(
        model_type: str, X_uri: str, y_uri: str, experiment_name: str = "",
        config: dict[str, Any] | None = None,
        model_config: TimeSeriesModelConfig | None = None,
    ) -> ToolResult[TrainTimeSeriesOutput]:
        """Train a time-series classifier on windowed features."""
        try:
            model_type_enum = TimeSeriesModelType(model_type)
            cfg = TimeSeriesTrainingConfig(**(config or {}))
            family_config = TimeSeriesModelConfig.model_validate(model_config) if model_config else None
            validate_model_config_for_family(model_type_enum, family_config)
        except (TypeError, ValueError) as error:
            return fail(str(error))
        emit_ml_event("ml.training.started", {
            "model_type": model_type_enum.value,
            "experiment_name": experiment_name, "status": "started",
        })
        try:
            if model_type_enum == TimeSeriesModelType.timegan:
                job = get_runtime().timegan_adapter.train(X_uri=X_uri, config=cfg, experiment_name=experiment_name)
            else:
                job = get_runtime().get_timeseries_trainer().train(
                    model_type=model_type_enum, X_uri=X_uri, y_uri=y_uri, config=cfg,
                    experiment_name=experiment_name, model_config=family_config,
                )
        except Exception as error:
            emit_ml_event("ml.training.failed", {
                "job_id": "", "model_type": model_type_enum.value,
                "experiment_name": experiment_name, "status": "failed",
                "error": str(error),
            })
            raise
        persist_training_run(job, experiment_name=experiment_name, source="mcp")
        emit_ml_event("ml.training.completed", {
            "job_id": job.id, "model_type": job.model_type.value,
            "experiment_name": experiment_name, "status": job.status,
            "metrics": job.metrics, "run_id": job.run_id,
        })
        return ok(TrainTimeSeriesOutput(
            job_id=job.id, model_type=job.model_type.value, status=job.status,
            experiment_id=job.experiment_id, run_id=job.run_id, metrics=job.metrics,
            model_path=job.model_path,
        ))

    @mcp.tool()
    @deterministic(input_model=PredictTimeSeriesInput, output_model=PredictTimeSeriesOutput)
    def ml_predict_timeseries(model_id: str, X_uri: str) -> ToolResult[PredictTimeSeriesOutput]:
        """Reject durable MLX; score only legacy non-passport backends."""
        from ..runtime.timeseries_factory import resolve_timeseries_backend
        if resolve_timeseries_backend() == "mlx":
            return fail("Durable MLX inference requires an exact promoted ModelPassport via ml_predict_neural_passport")
        try:
            predictions_uri = get_runtime().get_timeseries_trainer().predict(model_id, X_uri)
        except KeyError as error:
            return fail(str(error))
        return ok(PredictTimeSeriesOutput(model_id=model_id, predictions_uri=predictions_uri))

    @mcp.tool()
    @deterministic(input_model=CompareTimeSeriesInput, output_model=CompareTimeSeriesOutput)
    def ml_compare_timeseries(
        model_ids: list[str], metric: str = "auroc",
    ) -> ToolResult[CompareTimeSeriesOutput]:
        """Compare time-series models on a single metric (default: auroc)."""
        return ok(CompareTimeSeriesOutput.model_validate(
            get_runtime().get_timeseries_trainer().compare_models(model_ids, metric=metric),
        ))

    @mcp.tool()
    @deterministic(input_model=ListTimeSeriesModelsInput, output_model=ListTimeSeriesModelsOutput)
    def ml_list_timeseries_models() -> ToolResult[ListTimeSeriesModelsOutput]:
        """List all trained time-series models with summary fields."""
        models = get_runtime().get_timeseries_trainer().list_models()
        return ok(ListTimeSeriesModelsOutput(models=models, count=len(models)))

    @mcp.tool()
    @operational(input_model=SampleTimeSeriesInput, output_model=SampleTimeSeriesOutput)
    def ml_sample_timeseries(
        model_id: str, n_samples: int = 1000, seed: int = 42,
    ) -> ToolResult[SampleTimeSeriesOutput]:
        """Generate synthetic windows from a trained generative model."""
        try:
            samples_uri = get_runtime().timegan_adapter.sample(model_id, n_samples, seed=seed)
        except KeyError as error:
            return fail(str(error))
        return ok(SampleTimeSeriesOutput(
            model_id=model_id, samples_uri=samples_uri, n_samples=n_samples, seed=seed,
        ))

    @mcp.tool()
    @operational(input_model=ContinueTimeSeriesInput, output_model=ContinueTimeSeriesOutput)
    def ml_continue_timeseries(
        model_id: str, X_uri: str, experiment_name: str = "",
        config: dict[str, Any] | None = None,
        classifier_feedback: dict[str, float] | None = None,
    ) -> ToolResult[ContinueTimeSeriesOutput]:
        """Continue training a TimeGAN from a previous checkpoint."""
        cfg = TimeSeriesTrainingConfig(**(config or {})) if config else None
        emit_ml_event("ml.training.started", {
            "model_type": "timegan", "experiment_name": experiment_name,
            "status": "started", "parent_model_id": model_id,
        })
        try:
            job = get_runtime().timegan_adapter.continue_train(
                model_id=model_id, X_uri=X_uri, config=cfg, experiment_name=experiment_name,
                classifier_feedback=classifier_feedback,
            )
        except KeyError as error:
            emit_ml_event("ml.training.failed", {
                "job_id": "", "model_type": "timegan",
                "experiment_name": experiment_name, "status": "failed",
                "parent_model_id": model_id, "error": str(error),
            })
            return fail(str(error))
        except Exception as error:
            emit_ml_event("ml.training.failed", {
                "job_id": "", "model_type": "timegan",
                "experiment_name": experiment_name, "status": "failed",
                "parent_model_id": model_id, "error": str(error),
            })
            raise
        persist_training_run(job, experiment_name=experiment_name, source="mcp")
        emit_ml_event("ml.training.completed", {
            "job_id": job.id, "model_type": job.model_type.value,
            "experiment_name": experiment_name, "status": job.status,
            "metrics": job.metrics, "run_id": job.run_id,
            "parent_model_id": model_id,
        })
        return ok(ContinueTimeSeriesOutput(
            job_id=job.id, parent_model_id=model_id, model_type=job.model_type.value,
            status=job.status, metrics=job.metrics, model_path=job.model_path,
        ))


__all__ = ["register", "MemoryTimeSeriesTrainingAdapter"]
