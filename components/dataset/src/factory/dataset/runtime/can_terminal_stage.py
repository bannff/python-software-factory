"""Stable synchronous Dataset-stage execution for one CAN attempt."""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from .atomic_io import atomic_write_immutable, read_bytes_no_follow
from .base import DatasetExecutionPolicy, DatasetInputRef, DatasetSnapshotRef, DatasetToolSchemaSnapshotRef
from .can_terminal_canonical import canonical_json
from .can_terminal_paths import checked_output_path
from .contracts import DatasetArtifactRef, DatasetGenerationRequest, DatasetJobStatus
from .helpers import _now
from .local import LocalDatasetStore
from .materializer import LocalDatasetMaterializer


class CanTerminalStageRunner:
    """Run recipe stages inline with deterministic job identity and recovery."""

    def __init__(self, root: Path, attempt_id: str, request_sha256: str) -> None:
        self.root = root.resolve()
        self.attempt_id = attempt_id
        self.request_sha256 = request_sha256
        for name in ("jobs", "artifacts", "manifests", "checkpoints", "can_terminal"):
            checked_output_path(self.root, self.root / name)
        self.store = LocalDatasetStore(self.root)
        self.snapshots = self.root / "can_terminal" / "snapshots"

    def run(
        self, role: str, recipe_uri: str, input_uris: list[str],
        config: dict[str, Any], *, input_roles: list[str] | None = None,
    ) -> dict[str, Any]:
        request = self._request(role, recipe_uri, input_uris, config, input_roles)
        job_id = self._job_id(role)
        status = self.store.get_job(job_id)
        if status is None:
            status = DatasetJobStatus(
                job_id=job_id, status="queued", submitted_at=_now(), request=request,
            )
            self.store.save_job(status)
        elif status.request != request:
            raise ValueError(f"stable Dataset job request mismatch for {role}")
        if status.status == "completed":
            artifact = self.store.get_artifact(job_id)
            if artifact is None:
                raise ValueError(f"completed Dataset stage has no artifact: {role}")
            return _result(job_id, artifact)
        if status.status == "failed":
            raise ValueError(status.error or f"Dataset stage failed: {role}")
        recovered = self._recover_published(job_id, request)
        if recovered is not None:
            self._complete(status, recovered)
            return _result(job_id, recovered)
        running = self.store.claim_job(job_id)
        try:
            artifact = LocalDatasetMaterializer(self.store).materialize(running)
        except Exception as exc:
            self.store.save_job(running.model_copy(update={
                "status": "failed", "completed_at": _now(), "error": str(exc),
            }))
            raise
        self._complete(running, artifact)
        verified = self.store.get_artifact(job_id)
        if verified is None:
            raise ValueError(f"Dataset stage artifact verification failed: {role}")
        return _result(job_id, verified)

    def _complete(self, status: DatasetJobStatus, artifact: DatasetArtifactRef) -> None:
        self.store.save_job(status.model_copy(update={
            "status": "completed", "completed_at": _now(), "artifact": artifact,
            "error": None,
        }))

    def _recover_published(
        self, job_id: str, request: DatasetGenerationRequest,
    ) -> DatasetArtifactRef | None:
        from .artifact_utils import verify_artifact
        refs = sorted((self.store.artifacts_dir / job_id).glob("dataset-*.ref.json"))
        if not refs:
            return None
        if len(refs) != 1:
            raise ValueError(f"ambiguous published Dataset artifacts for {job_id}")
        artifact = DatasetArtifactRef.model_validate_json(
            read_bytes_no_follow(refs[0])
        )
        verify_artifact(
            artifact, self.store.manifests_dir, self.store.artifacts_dir,
            request=request,
        )
        return artifact

    def _request(
        self, role: str, recipe_uri: str, input_uris: list[str],
        config: dict[str, Any], input_roles: list[str] | None,
    ) -> DatasetGenerationRequest:
        if input_roles is not None and len(input_roles) != len(input_uris):
            raise ValueError("input roles must match stage inputs")
        inputs = []
        for index, value in enumerate(input_uris):
            path = _path(value)
            inputs.append(DatasetInputRef(
                uri=path.as_uri(), digest=hashlib.sha256(
                    read_bytes_no_follow(path)
                ).hexdigest(),
                artifact_role=input_roles[index] if input_roles else None,
            ))
        context = self._snapshot(f"{role}-context", {
            "stage_overrides": {_stage_name(recipe_uri): config},
        })
        tools = self._snapshot("tool-schema", {"allowed_tools": []})
        return DatasetGenerationRequest(
            recipe_uri=recipe_uri,
            recipe_digest=hashlib.sha256(recipe_uri.encode()).hexdigest(),
            input_artifacts=inputs,
            context_snapshot=DatasetSnapshotRef(**context),
            tool_schema_snapshot=DatasetToolSchemaSnapshotRef(
                **tools, allowed_tools=[],
            ),
            execution_policy=DatasetExecutionPolicy(
                fail_closed=True, retry_from_checkpoint_only=True,
            ),
            idempotency_key=f"{self.attempt_id}:{role}",
        )

    def _snapshot(self, label: str, value: dict[str, Any]) -> dict[str, str]:
        content = canonical_json(value)
        digest = hashlib.sha256(content).hexdigest()
        path = checked_output_path(
            self.root, self.snapshots / f"{label}-{digest}.json",
        )
        atomic_write_immutable(path, content)
        return {"uri": path.resolve().as_uri(), "digest": digest}

    def _job_id(self, role: str) -> str:
        return can_stage_job_id(self.attempt_id, self.request_sha256, role)


def can_stage_job_id(attempt_id: str, request_sha256: str, role: str) -> str:
    seed = f"{attempt_id}\0{request_sha256}\0{role}".encode()
    return f"can-{hashlib.sha256(seed).hexdigest()}"


def _stage_name(recipe_uri: str) -> str:
    prefix = "recipe://local/"
    if not recipe_uri.startswith(prefix) or "@" not in recipe_uri:
        raise ValueError(f"Unsupported Dataset terminal recipe URI: {recipe_uri}")
    if recipe_uri == "recipe://local/can-window@2":
        return "can_window_v2"
    return recipe_uri.removeprefix(prefix).split("@", 1)[0].replace("-", "_")


def _path(value: str) -> Path:
    from .recipe import path_from_uri
    path = path_from_uri(value) if value.startswith("file:") else Path(value).resolve()
    if not path.is_file():
        raise ValueError(f"Dataset stage input is missing: {value}")
    return path


def _result(job_id: str, artifact: DatasetArtifactRef) -> dict[str, Any]:
    return {
        "job_id": job_id, "dataset_uri": artifact.dataset_uri,
        "manifest_uri": artifact.manifest_uri, "digest": artifact.digest,
    }


__all__ = ["CanTerminalStageRunner", "can_stage_job_id"]
