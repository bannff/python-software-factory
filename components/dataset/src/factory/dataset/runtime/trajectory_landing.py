"""Frozen v1 JSONL contract for Evals trajectory landing rows.

Digest-only content: rows carry `sha256:<hex>` digests of upstream evidence and
never tenant/principal/user identity or inline text — any such key is rejected
loudly at ingress (the PII/tenant egress guard for the learning loop).
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, StrictStr

TRAJECTORY_ROW_SCHEMA_VERSION = 1
_DIGEST_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")

# Identity and inline-content keys are forbidden in landing rows even though
# `extra="forbid"` would already reject them; naming them gives a loud,
# targeted rejection reason at the ingress boundary.
FORBIDDEN_ROW_KEYS = frozenset({
    "tenant_id", "principal_id", "user_id", "nick", "text",
    "display_name", "email", "prompt_text", "completion_text",
    "input_summary", "output_summary",
})


class TrajectoryRowError(ValueError):
    """Stable rejection reason for a non-conforming trajectory row."""


class TrajectoryRow(BaseModel):
    """One trajectory-evidence row: attempt identity plus content digests only."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = TRAJECTORY_ROW_SCHEMA_VERSION
    run_id: StrictStr = Field(min_length=1)
    attempt_id: StrictStr = Field(min_length=1)
    recorded_at: StrictStr = Field(min_length=1)
    content_sha256: StrictStr
    verdict: StrictStr = ""

    @field_validator("content_sha256")
    @classmethod
    def _digest_shape(cls, value: str) -> str:
        if not _DIGEST_PATTERN.match(value):
            raise ValueError("content_sha256 must be a sha256:<64 hex chars> digest")
        return value


def _pre_validate(row: dict[str, Any]) -> None:
    if not isinstance(row, dict):
        raise TrajectoryRowError("trajectory row must be a JSON object")
    leaked = sorted(FORBIDDEN_ROW_KEYS & row.keys())
    if leaked:
        raise TrajectoryRowError(
            "trajectory row rejected: forbidden PII/tenant/content keys: "
            f"{leaked}"
        )


def validate_trajectory_row(row: dict[str, Any]) -> TrajectoryRow:
    """Validate one trajectory row against the frozen v1 contract."""
    _pre_validate(row)
    try:
        return TrajectoryRow.model_validate(row)
    except ValueError as exc:
        raise TrajectoryRowError(f"trajectory row rejected: {exc}") from exc


def validate_trajectory_rows(rows: list[dict[str, Any]]) -> list[TrajectoryRow]:
    """Validate a full landing-zone rowset."""
    return [validate_trajectory_row(row) for row in rows]


def trajectory_ref(row_count: int) -> dict[str, Any]:
    """Return the immutable reference payload for one landing-zone file."""
    return {"schema_version": TRAJECTORY_ROW_SCHEMA_VERSION, "row_count": row_count}


def parse_rowset(content: bytes) -> list[TrajectoryRow]:
    """Parse and validate a JSONL rowset, rejecting partial or bad rows."""
    rows = []
    for lineno, line in enumerate(content.decode("utf-8").splitlines(), start=1):
        if not line.strip():
            raise TrajectoryRowError(f"trajectory rowset has a partial row at line {lineno}")
        try:
            raw = json.loads(line)
        except ValueError as exc:
            raise TrajectoryRowError(f"trajectory rowset line {lineno} is not valid JSON: {exc}") from exc
        rows.append(validate_trajectory_row(raw))
    return rows


__all__ = [
    "FORBIDDEN_ROW_KEYS", "TRAJECTORY_ROW_SCHEMA_VERSION", "TrajectoryRow",
    "TrajectoryRowError", "parse_rowset", "trajectory_ref",
    "validate_trajectory_row", "validate_trajectory_rows",
]


DEFAULT_TRAJECTORY_LANDING_ROOT = ".storage/trajectory_landing"


def trajectory_zone_path(root: Path, run_id: str) -> Path:
    """Return the canonical rowset path for one run inside a landing root."""
    return Path(root) / f"{run_id}.jsonl"


def trajectory_zone_uri(root: Path, run_id: str) -> str:
    """Return the local file URI a resolver call accepts."""
    return trajectory_zone_path(root, run_id).resolve().as_uri()


def resolve_trajectory_zone(
    dataset_uri: str, storage_root: Path | None = None,
) -> dict[str, Any]:
    """Resolve a landing zone through a resolver-verified reference chain.

    Local-file trust is refused: the JSONL rowset is only returned when its
    SHA-256 digest matches the `ref.json` sidecar and every row passes the
    frozen v1 contract.
    """
    from .atomic_io import read_bytes_no_follow
    from .helpers import _sha256
    from .local_inputs import path_from_uri_no_follow

    if dataset_uri.startswith("file:"):
        path = path_from_uri_no_follow(dataset_uri)
    else:
        root = Path(storage_root or DEFAULT_TRAJECTORY_LANDING_ROOT)
        path = root / dataset_uri
    ref_path = path.parent / (path.name + ".ref.json")
    try:
        content = read_bytes_no_follow(path)
        ref = json.loads(read_bytes_no_follow(ref_path).decode("utf-8"))
    except OSError as exc:
        raise TrajectoryRowError(f"trajectory zone is unreadable: {exc}") from None
    if not isinstance(ref, dict) or not _DIGEST_PATTERN.match(str(ref.get("digest", ""))):
        raise TrajectoryRowError("trajectory zone reference is missing a valid digest")
    actual = f"sha256:{_sha256(content)}"
    if actual != ref["digest"]:
        raise TrajectoryRowError(
            "trajectory rowset tampered: digest does not match its reference"
        )
    rows = parse_rowset(content)
    if int(ref.get("row_count", -1)) != len(rows):
        raise TrajectoryRowError(
            f"trajectory rowset row_count mismatch: ref={ref.get('row_count')} "
            f"actual={len(rows)}"
        )
    return {"schema_version": TRAJECTORY_ROW_SCHEMA_VERSION, "digest": ref["digest"],
            "row_count": len(rows), "rows": [row.model_dump(mode="json") for row in rows]}


