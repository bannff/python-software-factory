"""Checkpoint serialization for :class:`PeftFineTuningAdapter`.

Split out to keep ``peft_finetuning.py`` under the 200-LOC ceiling.
"""

from __future__ import annotations

import uuid
from io import BytesIO
from typing import Any

import torch

from ..models import Checkpoint, CheckpointType, FineTuningJob

__all__ = ["save_lora_checkpoint"]


def save_lora_checkpoint(
    checkpoint_store: Any | None, job: FineTuningJob, result: dict[str, Any],
) -> Checkpoint:
    """Serialize the trained LoRA adapter weights via ``CheckpointStore.save``."""
    buf = BytesIO()
    torch.save(result["lora_state_dict"], buf)
    path = ""
    if checkpoint_store is not None:
        path = checkpoint_store.save(
            job.id, f"step_{result['step']}", buf.getvalue(),
            CheckpointType.final_artifact,
        )
    return Checkpoint(
        id=str(uuid.uuid4()), job_id=job.id, step=result["step"], path=path,
        checkpoint_type=CheckpointType.final_artifact,
        metrics={"loss": result["loss"]},
    )
