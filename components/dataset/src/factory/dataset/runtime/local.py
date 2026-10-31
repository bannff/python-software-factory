"""Local durable adapter for dataset jobs."""

from __future__ import annotations

import json
import re
import uuid
from pathlib import Path
from .artifact_utils import require_artifact_path, verify_artifact
from .atomic_io import read_bytes_no_follow
from .contracts import (
    DatasetArtifactRef,
    DatasetGenerationRequest,
    DatasetJobReceipt,
    DatasetJobStatus,
    DatasetManifest,
)
from .helpers import _file_uri, _now, _sha256  # noqa: F401 — backward-compat re-export

# Backward-compat re-export — canonical home is materializer.py
from .materializer import LocalDatasetMaterializer  # noqa: F401
from .recipe import path_from_uri
from .local_executor import LocalDatasetExecutor

_JOB_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}\Z")


def _require_job_id(job_id: str) -> None:
    if not isinstance(job_id, str) or _JOB_ID.fullmatch(job_id) is None:
        raise ValueError("Dataset job ID is invalid")


class LocalDatasetStore:
    """Filesystem-backed job store with atomic state transitions."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.jobs_dir = self.root / "jobs"
        self.artifacts_dir = self.root / "artifacts"
        self.manifests_dir = self.root / "manifests"
        for directory in (self.jobs_dir, self.artifacts_dir, self.manifests_dir):
            directory.mkdir(parents=True, exist_ok=True)

    def create_job(self, request: DatasetGenerationRequest) -> DatasetJobReceipt:
        receipt, _ = self.create_or_get_job(request)
        return receipt

    def create_or_get_job(self, request: DatasetGenerationRequest) -> tuple[DatasetJobReceipt, bool]:
        existing = self._find_existing_job(request)
        if existing is not None:
            return DatasetJobReceipt(job_id=existing.job_id, submitted_at=existing.submitted_at), False
        receipt = DatasetJobReceipt(job_id=str(uuid.uuid4()), submitted_at=_now())
        self.save_job(DatasetJobStatus(**receipt.model_dump(), request=request))
        return receipt, True

    def get_job(self, job_id: str) -> DatasetJobStatus | None:
        _require_job_id(job_id)
        path = self.jobs_dir / f"{job_id}.json"
        try:
            content = read_bytes_no_follow(path)
        except FileNotFoundError:
            return None
        status = DatasetJobStatus.model_validate_json(content)
        if status.job_id != job_id:
            raise ValueError("Dataset job identity differs from its file")
        if status.artifact is not None:
            if status.status != "completed":
                raise ValueError("Only a completed dataset job may expose an artifact")
            self._verified_artifact(status)
        elif status.status == "completed":
            raise ValueError("Completed dataset job has no artifact")
        return status

    def save_job(self, status: DatasetJobStatus) -> None:
        _require_job_id(status.job_id)
        self._write_json(self.jobs_dir / f"{status.job_id}.json", status.model_dump(mode="json"))

    def claim_job(self, job_id: str) -> DatasetJobStatus:
        """Use the durable job record as the lease: queued flips to running when claimed."""
        status = self.get_job(job_id)
        if status is None:
            raise ValueError(f"Unknown dataset job: {job_id}")
        if status.status == "queued":
            status = status.model_copy(update={"status": "running", "started_at": _now(), "error": None})
            self.save_job(status)
        elif status.status == "running" and status.started_at is None:
            status = status.model_copy(update={"started_at": _now()})
            self.save_job(status)
        return status

    def cancel_job(self, job_id: str, reason: str = "cancelled") -> DatasetJobStatus:
        status = self.get_job(job_id)
        if status is None:
            raise ValueError(f"Unknown dataset job: {job_id}")
        if status.status in {"completed", "failed"}:
            return status
        cancelled = status.model_copy(update={
            "status": "failed",
            "completed_at": _now(),
            "error": reason,
            "artifact": None,
            "cancelled_at": _now(),
        })
        self.save_job(cancelled)
        return cancelled

    def get_artifact(self, job_id: str) -> DatasetArtifactRef | None:
        status = self.get_job(job_id)
        if not status or status.status != "completed" or not status.artifact:
            return None
        return status.artifact

    def _verified_artifact(self, status: DatasetJobStatus) -> DatasetArtifactRef:
        if status.artifact is None:
            raise ValueError("Completed dataset job has no artifact")
        reference_path = path_from_uri(status.artifact.dataset_uri).with_suffix(".ref.json")
        require_artifact_path(path_from_uri(status.artifact.dataset_uri), reference_path, self.artifacts_dir)
        try:
            reference_content = read_bytes_no_follow(reference_path)
        except FileNotFoundError:
            raise ValueError("Dataset artifact reference is missing") from None
        artifact = DatasetArtifactRef.model_validate_json(reference_content)
        if artifact.dataset_uri != status.artifact.dataset_uri:
            raise ValueError("Dataset artifact reference does not belong to this job")
        verify_artifact(
            artifact, self.manifests_dir, self.artifacts_dir,
            request=status.request, expected_job_id=status.job_id,
        )
        if artifact != status.artifact:
            raise ValueError("Dataset artifact reference differs from completed job")
        return artifact

    def resolve_manifest(self, dataset_uri: str) -> DatasetManifest | None:
        artifact_path = path_from_uri(dataset_uri)
        reference_path = artifact_path.with_suffix(".ref.json")
        try:
            reference_content = read_bytes_no_follow(reference_path)
        except FileNotFoundError:
            return None
        require_artifact_path(artifact_path, reference_path, self.artifacts_dir)
        artifact = DatasetArtifactRef.model_validate_json(reference_content)
        if artifact.dataset_uri != dataset_uri or not artifact.manifest_uri:
            raise ValueError("Artifact reference does not match requested dataset URI")
        verify_artifact(artifact, self.manifests_dir, self.artifacts_dir)
        manifest = DatasetManifest.model_validate_json(
            read_bytes_no_follow(path_from_uri(artifact.manifest_uri))
        )
        return manifest.model_copy(update={
            "dataset_uri": artifact.dataset_uri,
            "manifest_uri": artifact.manifest_uri,
            "training_uri": artifact.training_uri,
        })

    def _find_existing_job(self, request: DatasetGenerationRequest) -> DatasetJobStatus | None:
        if request.idempotency_key is None:
            return None
        request_fingerprint = _request_digest(request)
        for path in sorted(self.jobs_dir.glob("*.json")):
            status = DatasetJobStatus.model_validate_json(read_bytes_no_follow(path))
            if status.request.idempotency_key != request.idempotency_key:
                continue
            if _request_digest(status.request) != request_fingerprint:
                raise ValueError("Dataset idempotency key already binds a different request")
            return status
        return None

    def _write_json(self, path: Path, value: object) -> None:
        from .atomic_io import atomic_write
        content = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
        atomic_write(path, content)


def _request_digest(request: DatasetGenerationRequest) -> str:
    request_content = json.dumps(
        request.model_dump(mode="json", exclude_none=True),
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return _sha256(request_content)


