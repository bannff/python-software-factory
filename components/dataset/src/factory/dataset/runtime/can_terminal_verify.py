"""Fail-closed verification of replayed CAN terminal outputs."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .can_terminal_paths import checked_output_path
from .atomic_io import read_bytes_no_follow
from .checkpoint_integrity import checkpoint_metadata_digest
from .contracts import DatasetManifest, DatasetStageCheckpoint
from .local import LocalDatasetStore
from .recipe import path_from_uri
from .can_terminal_stage import can_stage_job_id


def verify_terminal(
    root: Path, terminal: dict[str, Any], *, attempt_id: str,
    request_sha256: str, use_context: bool | None = None,
    expected_roles: set[str] | None = None,
) -> None:
    """Bind terminal identity and verify every artifact and stage lineage."""
    if terminal.get("attempt_id") != attempt_id:
        raise ValueError("CAN terminal attempt identity mismatch")
    if terminal.get("request_sha256") != request_sha256:
        raise ValueError("CAN terminal request identity mismatch")
    status = terminal.get("status")
    if status == "failed":
        if not isinstance(terminal.get("error"), str):
            raise ValueError("failed CAN terminal has no error")
        return
    if status != "completed":
        raise ValueError("CAN terminal status is invalid")
    resolved_root = root.resolve()
    _verify_artifacts(resolved_root, terminal.get("artifacts"))
    store = LocalDatasetStore(resolved_root)
    receipts = terminal.get("stage_receipts")
    if not isinstance(receipts, dict):
        raise ValueError("completed CAN terminal has no stage receipts")
    required = expected_roles or _required_roles(terminal["artifacts"], use_context)
    if set(receipts) != required:
        raise ValueError("CAN terminal stage receipt roles are incomplete")
    for role, receipt in receipts.items():
        if not isinstance(receipt, dict):
            raise ValueError(f"invalid Dataset stage receipt: {role}")
        job_id = receipt.get("job_id")
        expected_job = can_stage_job_id(attempt_id, request_sha256, role)
        if job_id != expected_job:
            raise ValueError(f"Dataset stage job identity mismatch: {role}")
        if not all(f"{role}:{kind}" in terminal["artifacts"]
                   for kind in ("dataset", "manifest", "reference")):
            raise ValueError(f"Dataset stage artifacts are incomplete: {role}")
        status_record = store.get_job(job_id)
        if status_record is None or status_record.request.idempotency_key != f"{attempt_id}:{role}":
            raise ValueError(f"Dataset stage request identity mismatch: {role}")
        artifact = store.get_artifact(job_id)
        if artifact is None:
            raise ValueError(f"Dataset stage artifact missing on replay: {role}")
        expected = {
            "job_id": job_id, "dataset_uri": artifact.dataset_uri,
            "manifest_uri": artifact.manifest_uri, "digest": artifact.digest,
        }
        if receipt != expected:
            raise ValueError(f"Dataset stage receipt disagrees with artifact: {role}")
        _verify_checkpoints(store, job_id, artifact.manifest_uri)


def _verify_artifacts(root: Path, artifacts: Any) -> None:
    if not isinstance(artifacts, dict) or not artifacts:
        raise ValueError("completed CAN terminal has no artifacts")
    for name, value in artifacts.items():
        if not isinstance(value, dict) or set(value) != {"uri", "sha256", "evidence"}:
            raise ValueError(f"invalid CAN terminal artifact entry: {name}")
        digest = value.get("sha256")
        if value.get("evidence") != {"sha256": digest}:
            raise ValueError(f"CAN terminal artifact evidence mismatch: {name}")
        path = checked_output_path(root, path_from_uri(str(value.get("uri"))))
        try:
            content = read_bytes_no_follow(path)
        except (FileNotFoundError, OSError):
            raise ValueError(f"CAN terminal artifact digest mismatch: {name}") from None
        if hashlib.sha256(content).hexdigest() != digest:
            raise ValueError(f"CAN terminal artifact digest mismatch: {name}")


def _required_roles(
    artifacts: dict[str, dict[str, Any]], use_context: bool | None,
) -> set[str]:
    if use_context is None:
        raise ValueError("CAN terminal context contract is required for verification")
    profile = artifacts.get("profile:dataset")
    if not isinstance(profile, dict):
        raise ValueError("CAN terminal profile artifact is missing")
    rows = [
        json.loads(line) for line in read_bytes_no_follow(
            path_from_uri(profile["uri"])
        ).splitlines()
        if line.strip()
    ]
    can_ids = rows[0].get("can_ids") if len(rows) == 1 else None
    if not isinstance(can_ids, dict) or not can_ids:
        raise ValueError("CAN terminal profile CAN-IDs are invalid")
    roles = {
        "ingest", "profile", "synthesize", "window", "augment",
        "prior_data_policy", *{f"signal_schema:{key}" for key in can_ids},
    }
    if use_context:
        roles.update({"context_ingest", "context_augment", "context_correlate"})
    return roles


def _verify_checkpoints(store: LocalDatasetStore, job_id: str, manifest_uri: str) -> None:
    manifest_path = checked_output_path(store.root, path_from_uri(manifest_uri))
    manifest = DatasetManifest.model_validate_json(read_bytes_no_follow(manifest_path))
    checkpoint_root = checked_output_path(
        store.root, store.root / "checkpoints" / job_id,
    )
    for expected in manifest.stage_lineage:
        path = checked_output_path(
            checkpoint_root,
            checkpoint_root / f"stage-{expected.stage_index}-{expected.output_digest}.checkpoint.json",
        )
        try:
            raw = read_bytes_no_follow(path)
        except OSError:
            raise ValueError("Dataset stage checkpoint metadata is missing") from None
        observed = DatasetStageCheckpoint.model_validate_json(raw)
        if raw != observed.model_dump_json(exclude_none=True).encode():
            raise ValueError("Dataset stage checkpoint bytes are not canonical")
        if observed != expected:
            raise ValueError("Dataset manifest and stage checkpoint disagree")
        if observed.checkpoint_digest != checkpoint_metadata_digest(observed):
            raise ValueError("Dataset stage checkpoint digest mismatch")
        output = checked_output_path(checkpoint_root, path_from_uri(observed.output_uri))
        try:
            output_content = read_bytes_no_follow(output)
        except OSError:
            raise ValueError("Dataset stage checkpoint output digest mismatch") from None
        if hashlib.sha256(output_content).hexdigest() != observed.output_digest:
            raise ValueError("Dataset stage checkpoint output digest mismatch")


__all__ = ["verify_terminal"]
