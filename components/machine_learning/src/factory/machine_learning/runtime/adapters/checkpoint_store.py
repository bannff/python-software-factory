"""Checkpoint storage — local filesystem or S3.

Default: ~/.factory/ml_checkpoints/
Override: ML_CHECKPOINT_PATH env var (supports s3:// prefix).
"""

from __future__ import annotations

import json
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..models import CheckpointType

_DEFAULT_LOCAL = os.path.expanduser("~/.factory/ml_checkpoints")


class CheckpointStore:
    """Stores checkpoint artifacts on local filesystem or S3."""

    def __init__(self, base_path: str | None = None) -> None:
        raw = base_path or os.environ.get("ML_CHECKPOINT_PATH") or _DEFAULT_LOCAL
        self._use_s3 = raw.startswith("s3://")
        if self._use_s3:
            self._s3_bucket, _, self._s3_prefix = raw[5:].partition("/")
        else:
            self._local_root = Path(raw)
            self._local_root.mkdir(parents=True, exist_ok=True)

    # -- public API ----------------------------------------------------

    def save(
        self,
        job_id: str,
        stage_or_step: str,
        data: bytes,
        checkpoint_type: CheckpointType,
    ) -> str:
        """Save checkpoint data, return storage path."""
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        name = f"{stage_or_step}_{ts}_{uuid.uuid4().hex[:8]}"
        if self._use_s3:
            return self._s3_save(job_id, name, data, checkpoint_type)
        return self._local_save(job_id, name, data, checkpoint_type)

    def load(self, path: str) -> bytes | None:
        """Load checkpoint data from path."""
        if path.startswith("s3://"):
            return self._s3_load(path)
        return self._local_load(path)

    def list(
        self,
        job_id: str,
        checkpoint_type: CheckpointType | None = None,
    ) -> list[dict[str, Any]]:
        """List checkpoints for a job, optionally filtered by type."""
        if self._use_s3:
            return self._s3_list(job_id, checkpoint_type)
        return self._local_list(job_id, checkpoint_type)

    def cleanup(
        self, older_than_days: int = 30, keep_best_n: int = 3,
    ) -> int:
        """Delete old checkpoints, return count deleted."""
        if self._use_s3:
            return 0  # S3 lifecycle policies handle this
        return self._local_cleanup(older_than_days, keep_best_n)

    # -- local filesystem ----------------------------------------------

    def _local_save(
        self, job_id: str, name: str, data: bytes, cp_type: CheckpointType,
    ) -> str:
        job_dir = self._local_root / job_id / cp_type.value
        job_dir.mkdir(parents=True, exist_ok=True)
        artifact = job_dir / name
        artifact.write_bytes(data)
        meta = {"type": cp_type.value, "created": time.time(), "size": len(data)}
        (job_dir / f"{name}.meta.json").write_text(json.dumps(meta))
        return str(artifact)

    def _local_load(self, path: str) -> bytes | None:
        p = Path(path)
        return p.read_bytes() if p.exists() else None

    def _local_list(
        self, job_id: str, cp_type: CheckpointType | None,
    ) -> list[dict[str, Any]]:
        job_dir = self._local_root / job_id
        if not job_dir.exists():
            return []
        results: list[dict[str, Any]] = []
        for type_dir in job_dir.iterdir():
            if not type_dir.is_dir():
                continue
            if cp_type and type_dir.name != cp_type.value:
                continue
            for meta_file in type_dir.glob("*.meta.json"):
                meta = json.loads(meta_file.read_text())
                artifact = meta_file.with_suffix("").with_suffix("")
                results.append({
                    "path": str(artifact),
                    "type": meta.get("type", type_dir.name),
                    "created": meta.get("created", 0),
                    "size": meta.get("size", 0),
                })
        return results

    def _local_cleanup(self, older_than_days: int, keep_best_n: int) -> int:
        cutoff = time.time() - (older_than_days * 86400)
        deleted = 0
        for job_dir in self._local_root.iterdir():
            if not job_dir.is_dir():
                continue
            for type_dir in job_dir.iterdir():
                if not type_dir.is_dir():
                    continue
                metas = sorted(
                    type_dir.glob("*.meta.json"),
                    key=lambda p: p.stat().st_mtime,
                    reverse=True,
                )
                for i, meta_file in enumerate(metas):
                    if i < keep_best_n:
                        continue
                    meta = json.loads(meta_file.read_text())
                    if meta.get("created", 0) < cutoff:
                        artifact = meta_file.with_suffix("").with_suffix("")
                        if artifact.exists():
                            artifact.unlink()
                        meta_file.unlink()
                        deleted += 1
        return deleted

    # -- S3 (lazy boto3) -----------------------------------------------

    def _s3_client(self) -> Any:
        import boto3  # noqa: lazy
        return boto3.client("s3")

    def _s3_key(self, job_id: str, name: str, cp_type: CheckpointType) -> str:
        prefix = f"{self._s3_prefix}/{job_id}/{cp_type.value}" if self._s3_prefix else f"{job_id}/{cp_type.value}"
        return f"{prefix}/{name}"

    def _s3_save(
        self, job_id: str, name: str, data: bytes, cp_type: CheckpointType,
    ) -> str:
        key = self._s3_key(job_id, name, cp_type)
        self._s3_client().put_object(Bucket=self._s3_bucket, Key=key, Body=data)
        return f"s3://{self._s3_bucket}/{key}"

    def _s3_load(self, path: str) -> bytes | None:
        bucket, _, key = path[5:].partition("/")
        try:
            resp = self._s3_client().get_object(Bucket=bucket, Key=key)
            return resp["Body"].read()
        except Exception:
            return None

    def _s3_list(
        self, job_id: str, cp_type: CheckpointType | None,
    ) -> list[dict[str, Any]]:
        prefix = f"{self._s3_prefix}/{job_id}" if self._s3_prefix else job_id
        if cp_type:
            prefix = f"{prefix}/{cp_type.value}"
        resp = self._s3_client().list_objects_v2(
            Bucket=self._s3_bucket, Prefix=prefix,
        )
        return [
            {"path": f"s3://{self._s3_bucket}/{o['Key']}", "size": o["Size"]}
            for o in resp.get("Contents", [])
            if not o["Key"].endswith(".meta.json")
        ]
