"""MLX process execution logic for fine-tuning."""

from __future__ import annotations

import logging
import re
import subprocess
import uuid
from datetime import datetime
from typing import Any, Callable

from ..emit import emit_ml_event
from ..finetuning_tracker import log_finetuning_run
from ..models import (
    Checkpoint,
    CheckpointType,
    FineTuningJob,
    JobStatus,
    ResolvedTrainingDataset,
)

logger = logging.getLogger(__name__)

# Captures `Iter 10: Train loss 2.345, ...` (actual mlx_lm output) AND the
# `[step 10/100] loss=2.345` form referenced in the spec. The separator
# between `loss` and the value is optional so both `loss=` and `loss ` work.
# Whichever match appears last in stdout wins, so the final reported loss
# is what we record.
_LOSS_PATTERN = re.compile(
    r"(?:Train\s+loss|loss)\s*[=:]?\s*(\d+\.\d+)",
    re.IGNORECASE,
)


def run_mlx_training(
    job: FineTuningJob,
    resolved: ResolvedTrainingDataset,
    persist_fn: Callable[[FineTuningJob], None],
    on_complete: Callable[[str], None]
) -> None:
    """Execute MLX training in a subprocess."""
    try:
        if job.training_input is None:
            raise ValueError("MLX training requires a dataset training input")

        cmd = _build_mlx_command(job, resolved)

        logger.info(f"Starting MLX job {job.id}: {' '.join(cmd)}")
        process = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
        )
        stdout, _ = process.communicate()

        if process.returncode == 0:
            metrics = _parse_metrics(stdout or "")
            job.status = JobStatus.completed
            job.metrics = metrics
            final_step = job.training_config.max_iters or 100
            cp = Checkpoint(
                id=str(uuid.uuid4()),
                job_id=job.id,
                step=final_step,
                path=f"mlx://{job.id}/adapters",
                metrics={**metrics, "step": float(final_step)},
            )
            job.checkpoints.append(cp)
        else:
            job.status = JobStatus.failed
            job.error = stdout[-500:] if stdout else "Unknown error"

    except Exception as e:
        job.status = JobStatus.failed
        job.error = str(e)
        logger.exception(f"MLX job {job.id} failed")
    finally:
        job.updated_at = datetime.now()
        event_type = "ml.finetuning.completed" if job.status == JobStatus.completed else "ml.finetuning.failed"
        emit_ml_event(event_type, {
            "job_id": job.id, "status": job.status.value,
            "metrics": job.metrics, "error": job.error
        })
        log_finetuning_run(
            job_id=job.id, base_model=job.base_model,
            method=job.method.value, status=job.status.value,
            metrics=job.metrics,
        )
        persist_fn(job)
        on_complete(job.id)


def _build_mlx_command(
    job: FineTuningJob, resolved: ResolvedTrainingDataset,
) -> list[str]:
    """Construct the ``mlx_lm lora`` CLI invocation from typed config objects."""
    cfg = job.training_config
    cmd: list[str] = [
        "python", "-m", "mlx_lm", "lora",
        "--model", job.base_model,
        "--train",
        "--data", _training_path(resolved.training_uri),
        "--iters", str(cfg.max_iters or 100),
        "--batch-size", str(cfg.batch_size or 4),
        "--learning-rate", str(cfg.learning_rate or 1e-4),
        "--max-seq-length", str(cfg.max_seq_length),
        "--seed", str(cfg.seed),
        "--grad-accumulation-steps", str(cfg.gradient_accumulation_steps),
        "--optimizer", cfg.optimizer,
    ]
    if cfg.grad_checkpoint:
        cmd.append("--grad-checkpoint")

    # LoRA hyperparameters (P0 fix for python-factory-dim.7): the runner used
    # to ignore job.lora_config entirely, so all jobs trained at the mlx_lm
    # default rank=8 / dropout=0 / scale=20. Forward every field the spec
    # promises callers can set; fall back gracefully if a field is absent on
    # older LoRAConfig subclasses.
    if job.lora_config is not None:
        lora = job.lora_config
        cmd.extend([
            "--lora-rank", str(lora.rank),
            "--lora-alpha", str(lora.alpha),
            "--lora-dropout", str(lora.dropout),
        ])
        if lora.target_modules:
            cmd.extend(["--target-modules", ",".join(lora.target_modules)])
        layers = getattr(lora, "layers", None)
        if layers is not None:
            cmd.extend(["--lora-layers", str(layers)])

    return cmd


def _parse_metrics(stdout: str) -> dict[str, float]:
    """Extract the final reported training loss from mlx_lm stdout.

    Returns an empty dict when no loss line is present (e.g. the model
    failed before the first report) so callers can still inspect the job.
    """
    matches = _LOSS_PATTERN.findall(stdout)
    if not matches:
        return {}
    try:
        return {"loss": float(matches[-1])}
    except ValueError:
        return {}


def _training_path(training_uri: str) -> str:
    """Convert the resolver's file URI into the local MLX path argument."""
    if not training_uri.startswith("file://"):
        raise ValueError("MLX training requires a file:// training URI")
    return training_uri.removeprefix("file://")
