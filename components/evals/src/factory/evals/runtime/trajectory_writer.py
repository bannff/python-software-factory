"""Atomic Trajectory landing-zone writer wired at the Evals persistence seams."""
from __future__ import annotations

import hashlib
import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any

from factory.dataset.interface import (
    DEFAULT_TRAJECTORY_LANDING_ROOT, TrajectoryRowError, trajectory_zone_path,
    trajectory_zone_uri, validate_trajectory_row,
)

logger = logging.getLogger(__name__)


def default_landing_root() -> Path:
    """Resolve the landing root from TRAJECTORY_LANDING_ZONE (or its default)."""
    return Path(os.environ.get("TRAJECTORY_LANDING_ZONE", DEFAULT_TRAJECTORY_LANDING_ROOT)).resolve()


def _atomic_write(path: Path, content: bytes) -> None:
    """Replace `path` atomically: a mid-write crash never lands a partial row."""
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    temp_path = Path(temp_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    except BaseException:
        if temp_path.exists():
            os.unlink(temp_path)
        raise


def append_trajectory_row(
    root: Path, *, run_id: str,
    attempt_id: str, content_sha256: str, recorded_at: str, verdict: str = "",
) -> str | None:
    """Append one validated row to a run's rowset and refresh its immutable ref.

    Returns the zone URI, or None when the (attempt_id, content_sha256) pair is
    already landed (idempotent replay). Validation failures fail loudly.
    """
    validated = validate_trajectory_row({
        "schema_version": 1, "run_id": run_id, "attempt_id": attempt_id,
        "recorded_at": recorded_at, "content_sha256": content_sha256,
        "verdict": verdict,
    })
    path = trajectory_zone_path(Path(root), run_id)
    rows = _load_rows(path)
    if any((row.get("attempt_id"), row.get("content_sha256")) == (attempt_id, content_sha256) for row in rows):
        return trajectory_zone_uri(Path(root), run_id)
    rows.append(validated.model_dump(mode="json"))
    content = ("\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n").encode("utf-8")
    digest = f"sha256:{hashlib.sha256(content).hexdigest()}"
    ref_path = path.parent / (path.name + ".ref.json")
    _atomic_write(path, content)
    _atomic_write(ref_path, json.dumps({"schema_version": 1, "row_count": len(rows), "digest": digest}).encode("utf-8"))
    return trajectory_zone_uri(Path(root), run_id)


def _load_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for lineno, line in enumerate(path.read_bytes().decode("utf-8").splitlines(), start=1):
        if not line.strip():
            raise TrajectoryRowError(f"landing zone {path.name} has a partial row at line {lineno}")
        rows.append(json.loads(line))
    return rows


def record_from_pointer(
    root: Path, pointer: dict[str, Any], *, run_id: str, attempt_id: str = "",
    recorded_at: str, verdict: str = "",
) -> str | None:
    """Land one idempotent row from an immutable Evals record pointer."""
    return append_trajectory_row(
        root, run_id=run_id, attempt_id=attempt_id or run_id,
        content_sha256=str(pointer.get("content_hash", "")),
        recorded_at=recorded_at, verdict=verdict,
    )


def best_effort_record(
    root: Path, pointer: Any, *, run_id: str, attempt_id: str = "",
    recorded_at: str = "", verdict: str = "",
) -> None:
    """Seam adapter: record landing failures, never break score persistence."""
    if not isinstance(pointer, dict) or not pointer.get("content_hash"):
        return
    try:
        record_from_pointer(root, pointer, run_id=run_id, attempt_id=attempt_id, recorded_at=recorded_at, verdict=verdict)
    except Exception as exc:
        logger.warning("trajectory landing write failed for run=%s: %s", run_id, exc)


__all__ = ["append_trajectory_row", "best_effort_record", "default_landing_root", "record_from_pointer"]
