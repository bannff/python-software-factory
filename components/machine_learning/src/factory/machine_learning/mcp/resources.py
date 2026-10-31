"""MCP resources for machine_learning."""

from __future__ import annotations

from typing import Callable

from typing import Any

from ..runtime.runtime import TrackingRuntime


def register(mcp: Any, get_runtime: Callable[[], TrackingRuntime]) -> None:
    """Register MCP resources."""

    @mcp.resource("tracking://experiments")
    def list_all_experiments() -> str:
        """List all experiments."""
        runtime = get_runtime()
        tracker = runtime.get_tracker()
        exps = tracker.list_experiments()
        lines = ["# Experiments", ""]
        for exp in exps:
            lines.append(f"- **{exp.name}** (`{exp.id}`)")
        if not exps:
            lines.append("No experiments yet.")
        return "\n".join(lines)

    @mcp.resource("tracking://experiments/{experiment_id}")
    def get_experiment_detail(experiment_id: str) -> str:
        """Get experiment details."""
        runtime = get_runtime()
        tracker = runtime.get_tracker()
        exp = tracker.get_experiment(experiment_id)
        if not exp:
            return f"# Experiment Not Found: {experiment_id}"
        return f"# {exp.name}\n\nID: `{exp.id}`\nDescription: {exp.description or 'N/A'}"

    @mcp.resource("tracking://health")
    def get_health_status() -> str:
        """Get tracking health status."""
        runtime = get_runtime()
        health = runtime.health_check()
        lines = ["# Tracking Health", ""]
        for name, status in health.items():
            icon = "✅" if status.healthy else "❌"
            lines.append(f"- {icon} **{name}**: {status.backend}")
        return "\n".join(lines)

    @mcp.resource("tracking://jobs")
    def list_finetuning_jobs() -> str:
        """List all fine-tuning jobs."""
        runtime = get_runtime()
        finetuner = runtime.get_finetuner()
        jobs = finetuner.list_jobs()
        lines = ["# Fine-Tuning Jobs", ""]
        for job in jobs:
            icon = {"completed": "✅", "running": "🔄", "failed": "❌", "pending": "⏳"}.get(job.status.value, "❓")
            lines.append(f"- {icon} **{job.id[:8]}** — {job.method.value} on `{job.base_model}` [{job.status.value}]")
        if not jobs:
            lines.append("No fine-tuning jobs yet.")
        return "\n".join(lines)

    @mcp.resource("tracking://docs")
    def get_docs() -> str:
        """Machine learning brick documentation."""
        return """# Machine Learning Brick

Experiment tracking and fine-tuning job management.

## Experiment Tracking
- Create experiments, start runs, log params/metrics
- Backends: memory, mlflow, tensorboard (default resolves from ML_TRACKER_BACKEND env; MLFLOW_TRACKING_URI passes through)

## Fine-Tuning
- Create and manage fine-tuning jobs
- Methods: lora, adalora, ia3, prefix_tuning, full, mlx_lora
- QLoRA: set quantization_bits=4 or 8 with any LoRA method
- Backends: memory (dev), mlx, huggingface, bedrock, openai (future)

## Quick Start
```
ml_create_finetuning_job(method="lora", base_model="model-id", dataset_uri="artifact://dataset-id", manifest_uri="artifact://manifest-id", dataset_digest="<sha256>", view_name="sft", view_schema_version="1.0")
ml_start_finetuning_job(job_id)
ml_get_job_status(job_id)
ml_export_model(job_id, "output/path")
```
"""
