"""Operational MCP tools for machine_learning."""
from __future__ import annotations

from typing import Callable
from typing import Any
from factory.mcp_utils.interface import ToolResult, operational
from ..runtime.models import DatasetTrainingInput, FineTuningMethod, LoRAConfig, TrainingConfig, TrainingObjective
from ..runtime.runtime import TrackingRuntime
from .operational_contracts import (
    CleanupCheckpointsInput, CleanupCheckpointsOutput, CreateExperimentInput,
    CreateFineTuningJobInput, EndRunInput, ExperimentOutput, ExportedModelOutput,
    ExportModelInput, FineTuningJobOutput, JobIdInput, LoggedFieldsOutput,
    LogMetricsInput, LogParamsInput, RunOutput, StartRunInput,
)


def register(mcp: Any, get_runtime: Callable[[], TrackingRuntime]) -> None:
    """Register typed operational tools."""
    @mcp.tool()
    @operational(input_model=CreateExperimentInput, output_model=ExperimentOutput)
    def tracking_create_experiment(name: str, description: str = "") -> ToolResult[ExperimentOutput]:
        exp = get_runtime().get_tracker().create_experiment(name, description)
        return ExperimentOutput(id=exp.id, name=exp.name, description=exp.description)

    @mcp.tool()
    @operational(input_model=StartRunInput, output_model=RunOutput)
    def tracking_start_run(experiment_id: str, name: str = "") -> ToolResult[RunOutput]:
        run = get_runtime().get_tracker().start_run(experiment_id, name)
        return RunOutput(id=run.id, experiment_id=run.experiment_id, name=run.name, status=run.status)

    @mcp.tool()
    @operational(input_model=EndRunInput, output_model=RunOutput)
    def tracking_end_run(run_id: str, status: str = "completed") -> ToolResult[RunOutput]:
        run = get_runtime().get_tracker().end_run(run_id, status)
        return RunOutput(id=run.id, status=run.status)

    @mcp.tool()
    @operational(input_model=LogParamsInput, output_model=LoggedFieldsOutput)
    def tracking_log_params(run_id: str, params: dict) -> ToolResult[LoggedFieldsOutput]:
        get_runtime().get_tracker().log_params(run_id, params)
        return LoggedFieldsOutput(run_id=run_id, logged=list(params))

    @mcp.tool()
    @operational(input_model=LogMetricsInput, output_model=LoggedFieldsOutput)
    def tracking_log_metrics(run_id: str, metrics: dict, step: int = 0) -> ToolResult[LoggedFieldsOutput]:
        get_runtime().get_tracker().log_metrics(run_id, metrics, step)
        return LoggedFieldsOutput(run_id=run_id, logged=list(metrics), step=step)

    @mcp.tool()
    @operational(input_model=CreateFineTuningJobInput, output_model=FineTuningJobOutput)
    def ml_create_finetuning_job(method: str, base_model: str, dataset_uri: str, manifest_uri: str, dataset_digest: str, view_name: str, view_schema_version: str, training_objective: str | None = None, batch_size: int = 4, learning_rate: float = 1e-4, max_iters: int | None = None, epochs: int | None = None, max_seq_length: int = 512, lora_rank: int = 8, lora_alpha: int = 16, lora_dropout: float = 0.05, quantization_bits: int | None = None) -> ToolResult[FineTuningJobOutput]:
        ft_method = FineTuningMethod(method)
        lora = LoRAConfig(rank=lora_rank, alpha=lora_alpha, dropout=lora_dropout, quantization_bits=quantization_bits) if ft_method in {FineTuningMethod.lora, FineTuningMethod.adalora, FineTuningMethod.mlx_lora} else None
        config = TrainingConfig(batch_size=batch_size, learning_rate=learning_rate, max_iters=max_iters, epochs=epochs, max_seq_length=max_seq_length)
        training = DatasetTrainingInput(dataset_uri=dataset_uri, manifest_uri=manifest_uri, dataset_digest=dataset_digest, view_name=view_name, view_schema_version=view_schema_version)
        objective = TrainingObjective(training_objective) if training_objective else None
        backend = "mlx" if ft_method == FineTuningMethod.mlx_lora else "memory"
        job = get_runtime().get_finetuner(backend).create_job(ft_method, base_model, training, config, lora, objective)
        return FineTuningJobOutput(id=job.id, status=job.status.value, method=job.method.value, training_objective=job.training_objective.value if job.training_objective else None, training_input=_serialize_training_input(job.training_input))

    @mcp.tool()
    @operational(input_model=JobIdInput, output_model=FineTuningJobOutput)
    def ml_start_finetuning_job(job_id: str) -> ToolResult[FineTuningJobOutput]:
        job = get_runtime().get_finetuner().start_job(job_id)
        return FineTuningJobOutput(id=job.id, status=job.status.value, metrics=job.metrics, checkpoints=len(job.checkpoints))

    @mcp.tool()
    @operational(input_model=JobIdInput, output_model=FineTuningJobOutput)
    def ml_stop_finetuning_job(job_id: str) -> ToolResult[FineTuningJobOutput]:
        job = get_runtime().get_finetuner().stop_job(job_id)
        return FineTuningJobOutput(id=job.id, status=job.status.value)

    @mcp.tool()
    @operational(input_model=ExportModelInput, output_model=ExportedModelOutput)
    def ml_export_model(job_id: str, destination: str) -> ToolResult[ExportedModelOutput]:
        artifact = get_runtime().get_finetuner().export_model(job_id, destination)
        return ExportedModelOutput(id=artifact.id, base_model=artifact.base_model, adapter_path=artifact.adapter_path, source_job_id=artifact.source_job_id)

    @mcp.tool()
    @operational(input_model=CleanupCheckpointsInput, output_model=CleanupCheckpointsOutput)
    def ml_cleanup_checkpoints(older_than_days: int = 30, keep_best_n: int = 3) -> ToolResult[CleanupCheckpointsOutput]:
        deleted = get_runtime().get_finetuner().cleanup_checkpoints(older_than_days, keep_best_n)
        return CleanupCheckpointsOutput(deleted=deleted, older_than_days=older_than_days, kept=keep_best_n)


def _serialize_training_input(value: DatasetTrainingInput | None) -> dict[str, str] | None:
    if value is None:
        return None
    return {key: getattr(value, key) for key in ("dataset_uri", "manifest_uri", "dataset_digest", "view_name", "view_schema_version")}
