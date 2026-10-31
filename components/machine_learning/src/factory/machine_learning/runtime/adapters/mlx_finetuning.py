"""MLX fine-tuning adapter for Apple Silicon."""

from __future__ import annotations

import uuid
import logging
import threading
import subprocess
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

logger = logging.getLogger(__name__)


class MlxFineTuningAdapter:
    """MLX fine-tuning backend \u2014 launches actual MLX LoRA processes."""

    def __init__(
        self,
        checkpoint_store: Any | None = None,
        dataset_resolver: Any | None = None,
        **kwargs: Any,
    ) -> None:
        self._jobs: dict[str, FineTuningJob] = {}
        self._artifacts: dict[str, ModelArtifact] = {}
        self._checkpoint_store = checkpoint_store
        self._dataset_resolver = dataset_resolver
        self._active_processes: dict[str, subprocess.Popen] = {}

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
        """Transition job to running and spawn background thread."""
        job = self._require_job(job_id)
        if job.status != JobStatus.pending:
            raise ValueError(f"Cannot start job in '{job.status.value}' state")

        try:
            resolved = self._resolve_training_dataset(job)
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
            "job_id": job_id, "base_model": job.base_model,
            "method": job.method.value,
        })
        self._persist(job)
        
        # Spawn background training thread
        thread = threading.Thread(
            target=self._training_worker, 
            args=(job_id, resolved),
            daemon=True
        )
        thread.start()
        
        return job

    def _resolve_training_dataset(self, job: FineTuningJob) -> ResolvedTrainingDataset:
        from .dataset_resolver import resolve_and_verify
        return resolve_and_verify(self._dataset_resolver, job.training_input)

    def _training_worker(
        self, job_id: str, resolved: ResolvedTrainingDataset,
    ) -> None:
        from .mlx_runner import run_mlx_training
        job = self._require_job(job_id)
        run_mlx_training(
            job,
            resolved,
            self._persist, 
            lambda jid: self._active_processes.pop(jid, None)
        )


    def get_job(self, job_id: str) -> FineTuningJob | None:
        """Get a job by ID."""
        return self._jobs.get(job_id)

    def list_jobs(self) -> list[FineTuningJob]:
        """List all fine-tuning jobs."""
        return list(self._jobs.values())

    def stop_job(self, job_id: str) -> FineTuningJob:
        """Stop a running job."""
        job = self._require_job(job_id)
        if job.status not in (JobStatus.pending, JobStatus.running):
            raise ValueError(f"Cannot stop job in '{job.status.value}' state")
        
        process = self._active_processes.get(job_id)
        if process:
            process.terminate()
            
        job.status = JobStatus.stopped
        job.updated_at = datetime.now()
        emit_ml_event("ml.finetuning.stopped", {
            "job_id": job_id, "previous_status": "running",
        })
        self._persist(job)
        return job

    def list_checkpoints(self, job_id: str) -> list[Checkpoint]:
        """List checkpoints for a job."""
        job = self._require_job(job_id)
        return list(job.checkpoints)

    def export_model(self, job_id: str, destination: str) -> ModelArtifact:
        """Export model artifact from a completed job."""
        job = self._require_job(job_id)
        if job.status != JobStatus.completed:
            raise ValueError(f"Cannot export from '{job.status.value}' job")
        artifact = ModelArtifact(
            id=str(uuid.uuid4()),
            base_model=job.base_model,
            adapter_path=destination,
            quantization_bits=(
                job.lora_config.quantization_bits if job.lora_config else None
            ),
            source_job_id=job_id,
        )
        self._artifacts[artifact.id] = artifact
        return artifact

    def cleanup_checkpoints(
        self, older_than_days: int = 30, keep_best_n: int = 3,
    ) -> int:
        """Delete old checkpoints via the checkpoint store."""
        if self._checkpoint_store:
            return self._checkpoint_store.cleanup(older_than_days, keep_best_n)
        return 0

    def list_stage_artifacts(self, job_id: str) -> list[Checkpoint]:
        """List stage_artifact checkpoints for a job."""
        job = self._require_job(job_id)
        return [
            cp for cp in job.checkpoints
            if cp.checkpoint_type == CheckpointType.stage_artifact
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
            logger.warning(f"Failed to persist graph job {job.id}: {e}")
