"""Generic PEFT/LoRA fine-tuning adapter — real training, any HF text model.

Implements :class:`FineTuningPort` fully, mirroring the lifecycle
pattern of :class:`MemoryFineTuningAdapter` / :class:`MlxFineTuningAdapter`
(pending -> running -> completed/failed, ``ml.finetuning.*`` events)
but with REAL behavior: ``start_job`` resolves the training dataset via
the shared :func:`dataset_resolver.resolve_and_verify` pattern, loads
``job.base_model`` with ``transformers.AutoModelForCausalLM``, wraps
it with ``peft.get_peft_model`` via the shared
:func:`peft_helpers.build_peft_lora_config`, and runs a real training
loop (:mod:`_peft_training_loop`). Real loss values land in
``job.metrics`` and a real :class:`Checkpoint` is written through
:class:`CheckpointStore.save` — no fabricated numbers.

bd:python-factory-q1jsr .5/.6 — the generic PEFT backend that fixes
the misplaced Chronos-only ``peft`` dependency and makes LoRA/PEFT a
first-class capability independent of any one model family.
"""

from __future__ import annotations

import logging
import threading
import uuid
from datetime import datetime
from typing import Any

from ..emit import emit_ml_event
from ..finetuning_tracker import log_finetuning_run
from ..models import (
    Checkpoint,
    CheckpointType,
    DatasetTrainingInput,
    FineTuningJob,
    FineTuningMethod,
    JobStatus,
    LoRAConfig,
    ModelArtifact,
    ResolvedTrainingDataset,
    TrainingConfig,
    TrainingObjective,
)
from ._peft_checkpoint import save_lora_checkpoint

logger = logging.getLogger(__name__)


class PeftFineTuningAdapter:
    """Real PEFT/LoRA fine-tuning backend for arbitrary HF causal-LM models."""

    def __init__(
        self, checkpoint_store: Any | None = None, dataset_resolver: Any | None = None,
        **kwargs: Any,
    ) -> None:
        self._jobs: dict[str, FineTuningJob] = {}
        self._artifacts: dict[str, ModelArtifact] = {}
        self._checkpoint_store = checkpoint_store
        self._dataset_resolver = dataset_resolver

    def create_job(
        self,
        method: FineTuningMethod,
        base_model: str,
        training_input: DatasetTrainingInput,
        training_config: TrainingConfig | None = None,
        lora_config: LoRAConfig | None = None,
        training_objective: TrainingObjective | None = None,
    ) -> FineTuningJob:
        """Create a pending fine-tuning job."""
        job = FineTuningJob(
            id=str(uuid.uuid4()),
            method=method,
            base_model=base_model,
            training_input=training_input,
            training_objective=training_objective,
            training_config=training_config or TrainingConfig(),
            lora_config=lora_config,
        )
        self._jobs[job.id] = job
        self._persist(job)
        return job

    def start_job(self, job_id: str) -> FineTuningJob:
        """Resolve the dataset, then run real training in a background thread."""
        job = self._require_job(job_id)
        if job.status != JobStatus.pending:
            raise ValueError(f"Cannot start job in '{job.status.value}' state")

        try:
            from .dataset_resolver import resolve_and_verify
            resolved = resolve_and_verify(self._dataset_resolver, job.training_input)
        except Exception as exc:
            job.status = JobStatus.failed
            job.error = str(exc)
            job.updated_at = datetime.now()
            self._persist(job)
            emit_ml_event("ml.finetuning.failed", {
                "job_id": job_id, "status": job.status.value, "error": job.error,
            })
            log_finetuning_run(
                job_id=job_id, base_model=job.base_model,
                method=job.method.value, status=job.status.value,
            )
            return job

        job.status = JobStatus.running
        job.updated_at = datetime.now()
        emit_ml_event("ml.finetuning.started", {
            "job_id": job_id, "base_model": job.base_model, "method": job.method.value,
        })
        self._persist(job)

        thread = threading.Thread(
            target=self._training_worker, args=(job_id, resolved), daemon=True,
        )
        thread.start()
        return job

    def _training_worker(self, job_id: str, resolved: ResolvedTrainingDataset) -> None:
        job = self._require_job(job_id)
        try:
            from ._peft_training_loop import run_peft_training
            result = run_peft_training(
                job.base_model, resolved, job.training_config, job.lora_config,
            )
            job.metrics = {"loss": result["loss"], "step": float(result["step"])}
            job.status = JobStatus.completed
            job.checkpoints.append(
                save_lora_checkpoint(self._checkpoint_store, job, result),
            )
        except Exception as exc:
            job.status = JobStatus.failed
            job.error = str(exc)
            logger.exception("PEFT fine-tuning job %s failed", job_id)
        finally:
            job.updated_at = datetime.now()
            event_type = (
                "ml.finetuning.completed" if job.status == JobStatus.completed
                else "ml.finetuning.failed"
            )
            emit_ml_event(event_type, {
                "job_id": job_id, "status": job.status.value,
                "metrics": job.metrics, "error": job.error,
            })
            log_finetuning_run(
                job_id=job_id, base_model=job.base_model,
                method=job.method.value, status=job.status.value,
                metrics=job.metrics,
            )
            self._persist(job)

    def get_job(self, job_id: str) -> FineTuningJob | None:
        return self._jobs.get(job_id)

    def list_jobs(self) -> list[FineTuningJob]:
        return list(self._jobs.values())

    def stop_job(self, job_id: str) -> FineTuningJob:
        job = self._require_job(job_id)
        if job.status not in (JobStatus.pending, JobStatus.running):
            raise ValueError(f"Cannot stop job in '{job.status.value}' state")
        job.status = JobStatus.stopped
        job.updated_at = datetime.now()
        emit_ml_event("ml.finetuning.stopped", {
            "job_id": job_id, "previous_status": "running",
        })
        self._persist(job)
        return job

    def list_checkpoints(self, job_id: str) -> list[Checkpoint]:
        job = self._require_job(job_id)
        return list(job.checkpoints)

    def export_model(self, job_id: str, destination: str) -> ModelArtifact:
        job = self._require_job(job_id)
        if job.status != JobStatus.completed:
            raise ValueError(f"Cannot export from '{job.status.value}' job")
        artifact = ModelArtifact(
            id=str(uuid.uuid4()), base_model=job.base_model, adapter_path=destination,
            quantization_bits=job.lora_config.quantization_bits if job.lora_config else None,
            source_job_id=job_id,
        )
        self._artifacts[artifact.id] = artifact
        return artifact

    def cleanup_checkpoints(self, older_than_days: int = 30, keep_best_n: int = 3) -> int:
        if self._checkpoint_store:
            return self._checkpoint_store.cleanup(older_than_days, keep_best_n)
        return 0

    def list_stage_artifacts(self, job_id: str) -> list[Checkpoint]:
        job = self._require_job(job_id)
        return [
            cp for cp in job.checkpoints if cp.checkpoint_type == CheckpointType.stage_artifact
        ]

    def _require_job(self, job_id: str) -> FineTuningJob:
        job = self._jobs.get(job_id)
        if not job:
            raise KeyError(f"Job not found: {job_id}")
        return job

    def _persist(self, job: FineTuningJob) -> None:
        """Persist to knowledge graph (fire-and-forget, never blocks)."""
        try:
            from .graph_adapter import GraphMLStore
            GraphMLStore().persist_job(job)
        except Exception as e:
            logger.warning("Failed to persist graph job %s: %s", job.id, e)
