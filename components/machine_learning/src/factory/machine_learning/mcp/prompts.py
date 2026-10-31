"""MCP prompts for machine_learning."""

from __future__ import annotations

from typing import Callable

from typing import Any

from ..runtime.runtime import TrackingRuntime


def register(mcp: Any, get_runtime: Callable[[], TrackingRuntime]) -> None:
    """Register MCP prompts."""

    @mcp.prompt()
    def run_experiment() -> str:
        """Guide for running an ML experiment."""
        return """# Run an ML Experiment

## Step 1: Create or Select Experiment
```
tracking_create_experiment("my-experiment", "Description")
```

## Step 2: Start a Run
```
tracking_start_run(experiment_id, "run-name")
```

## Step 3: Log Parameters and Metrics
```
tracking_log_params(run_id, {"learning_rate": 0.001, "batch_size": 32})
tracking_log_metrics(run_id, {"loss": loss, "accuracy": acc}, step)
```

## Step 4: End Run
```
tracking_end_run(run_id, "completed")
```
"""

    @mcp.prompt()
    def create_finetuning_job() -> str:
        """Guide for creating and running a fine-tuning job."""
        backends = TrackingRuntime.available_finetuning_backends()
        return f"""# Create a Fine-Tuning Job

Available backends: {', '.join(backends)}

## Step 1: List available methods
```
ml_list_finetuning_methods()
```

## Step 2: Create a job
```
ml_create_finetuning_job(
    method="lora",           # lora, adalora, ia3, prefix_tuning, full, mlx_lora
    base_model="model-id",   # HuggingFace model ID or local path
    dataset_uri="artifact://dataset-id",
    manifest_uri="artifact://manifest-id",
    dataset_digest="<sha256>",
    view_name="sft",
    view_schema_version="1.0",
    lora_rank=8,             # LoRA rank (lora/adalora/mlx_lora only)
    lora_alpha=16,           # LoRA alpha
    quantization_bits=None,  # 4 or 8 for QLoRA, None for float
    batch_size=4,
    learning_rate=1e-4,
    max_seq_length=512,
)
```

## Step 3: Start training
```
ml_start_finetuning_job(job_id)
```

## Step 4: Monitor progress
```
ml_get_job_status(job_id)
ml_list_checkpoints(job_id)
```

## Step 5: Export model
```
ml_export_model(job_id, "output/path")
```
"""

    @mcp.prompt()
    def debug_finetuning_job() -> str:
        """Guide for troubleshooting a failed fine-tuning job."""
        return """# Debug a Fine-Tuning Job

## Step 1: Check job status
```
ml_get_job_status(job_id)
```
Look at the `error` field and `status` for clues.

## Step 2: Review checkpoints
```
ml_list_checkpoints(job_id)
```
If checkpoints exist, training progressed before failing.

## Common issues:
- **OOM**: Reduce batch_size, max_seq_length, or lora_rank
- **Divergence**: Lower learning_rate, increase grad_accumulation
- **Slow training**: Enable grad_checkpoint, try mlx_lora on Apple Silicon
- **QLoRA issues**: Ensure quantization_bits is 4 or 8, not other values
"""
