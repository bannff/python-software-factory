"""Detached CLI worker for local durable dataset materialization."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
import sys

from .runtime.local import LocalDatasetMaterializer, LocalDatasetStore


def main(storage_root: Path, job_id: str) -> None:
    """Execute one queued job outside the request path."""
    print(f"dataset worker starting job={job_id} root={storage_root}", flush=True)
    store = LocalDatasetStore(storage_root)
    status = store.claim_job(job_id)
    if status.status != "running":
        return
    try:
        artifact = LocalDatasetMaterializer(store).materialize(status)
        current = store.get_job(job_id)
        if current is None:
            raise RuntimeError(f"Dataset job disappeared during execution: {job_id}")
        if current.status == "failed" and current.cancelled_at is not None:
            return
        store.save_job(
            current.model_copy(
                update={
                    "status": "completed",
                    "artifact": artifact,
                    "completed_at": datetime.now(UTC),
                    "error": None,
                }
            )
        )
    except Exception as error:
        current = store.get_job(job_id)
        if current is None:
            raise
        if current.status == "failed" and current.cancelled_at is not None:
            raise
        store.save_job(
            current.model_copy(
                update={
                    "status": "failed",
                    "completed_at": datetime.now(UTC),
                    "error": str(error),
                }
            )
        )
        raise


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("Usage: python -m factory.dataset.cli <storage_root> <job_id>")
    main(Path(sys.argv[1]), sys.argv[2])
