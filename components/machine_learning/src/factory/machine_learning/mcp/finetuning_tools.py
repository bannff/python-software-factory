"""Deterministic MCP tools for fine-tuning queries."""
from __future__ import annotations

from typing import Any, Callable
from factory.mcp_utils.interface import ToolResult, deterministic
from ..runtime.models import FineTuningMethod
from ..runtime.runtime import TrackingRuntime
from .finetuning_contracts import (
    CheckpointItem, CheckpointsOutput, EmptyInput, FineTuningJobDetails,
    FineTuningJobOutput, FineTuningJobsOutput, FineTuningMethodsOutput,
    JobIdInput, JobStatusOutput, StageArtifactsOutput,
)


def register(mcp: Any, get_runtime: Callable[[], TrackingRuntime]) -> None:
    """Register typed fine-tuning read-only tools."""
    @mcp.tool()
    @deterministic(input_model=EmptyInput, output_model=FineTuningMethodsOutput)
    def ml_list_finetuning_methods() -> ToolResult[FineTuningMethodsOutput]:
        descriptions = {"lora": "Low-Rank Adaptation — 0.1-1% params", "adalora": "Adaptive LoRA — auto rank per layer", "ia3": "Inhibiting and Amplifying — <0.1% params", "prefix_tuning": "Virtual token prefixes", "full": "Full fine-tuning — all parameters", "mlx_lora": "MLX-LM LoRA — Apple Silicon"}
        return FineTuningMethodsOutput(methods=[{"name": item.value, "description": descriptions[item.value]} for item in FineTuningMethod])

    @mcp.tool()
    @deterministic(input_model=JobIdInput, output_model=JobStatusOutput)
    def ml_get_job_status(job_id: str) -> ToolResult[JobStatusOutput]:
        job = get_runtime().get_finetuner().get_job(job_id)
        if not job:
            return JobStatusOutput(found=False)
        return JobStatusOutput(found=True, id=job.id, status=job.status.value, method=job.method.value, base_model=job.base_model, metrics=job.metrics, training_objective=job.training_objective.value if job.training_objective else None, checkpoints=len(job.checkpoints), error=job.error)

    @mcp.tool()
    @deterministic(input_model=EmptyInput, output_model=FineTuningJobsOutput)
    def ml_list_finetuning_jobs() -> ToolResult[FineTuningJobsOutput]:
        jobs = [_serialize_job(job) for job in get_runtime().get_finetuner().list_jobs()]
        return FineTuningJobsOutput(jobs=jobs, count=len(jobs))

    @mcp.tool()
    @deterministic(input_model=JobIdInput, output_model=FineTuningJobOutput)
    def ml_get_finetuning_job(job_id: str) -> ToolResult[FineTuningJobOutput]:
        job = get_runtime().get_finetuner().get_job(job_id)
        return FineTuningJobOutput(found=False) if not job else FineTuningJobOutput(found=True, **_serialize_job(job).model_dump())

    @mcp.tool()
    @deterministic(input_model=JobIdInput, output_model=CheckpointsOutput)
    def ml_list_checkpoints(job_id: str) -> ToolResult[CheckpointsOutput]:
        return CheckpointsOutput(job_id=job_id, checkpoints=_checkpoints(get_runtime().get_finetuner().list_checkpoints(job_id)))

    @mcp.tool()
    @deterministic(input_model=JobIdInput, output_model=StageArtifactsOutput)
    def ml_list_stage_artifacts(job_id: str) -> ToolResult[StageArtifactsOutput]:
        return StageArtifactsOutput(job_id=job_id, artifacts=_checkpoints(get_runtime().get_finetuner().list_stage_artifacts(job_id)))


def _checkpoints(items: list[Any]) -> list[CheckpointItem]:
    return [CheckpointItem(id=item.id, step=item.step, path=item.path, type=item.checkpoint_type.value, metrics=item.metrics) for item in items]


def _serialize_job(job: Any) -> FineTuningJobDetails:
    lora, config = job.lora_config, job.training_config
    training = job.training_input
    return FineTuningJobDetails(id=job.id, status=job.status.value, method=job.method.value, base_model=job.base_model, training_input=None if training is None else {key: getattr(training, key) for key in ("dataset_uri", "manifest_uri", "dataset_digest", "view_name", "view_schema_version")}, training_objective=job.training_objective.value if job.training_objective else None, loss=job.metrics.get("loss"), lora_rank=lora.rank if lora else None, learning_rate=config.learning_rate if config else None, checkpoints=len(job.checkpoints), error=job.error)
