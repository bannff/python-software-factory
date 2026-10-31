"""Dataset MCP orchestration for CAN policy and per-CAN signal schemas."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Callable

from .can_artifact_refs import CanDatasetArtifactRef
from .can_feature_schema import dataset_artifact_ref
from .can_keystone_dataset_payload import uri_to_path

DEFAULT_PRIOR_CONTEXT = [
    "aggressiveness_score", "battery_health_pct", "humidity_pct", "lat", "lon",
    "odometer_km", "precipitation_mm", "temp_c",
]


def load_can_profile(profile_uri: str) -> tuple[dict[str, Any], bytes]:
    """Load and validate the single Dataset-issued CAN profile record."""
    profile_path = uri_to_path(profile_uri)
    if profile_path is None:
        raise ValueError("CAN profile URI must reference a local file")
    if not profile_path.is_file():
        raise ValueError("CAN profile file is missing")
    try:
        profile_raw = profile_path.read_bytes()
    except OSError:
        raise ValueError("CAN profile file is unreadable") from None
    try:
        profile = _single_record(profile_raw)
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise ValueError("CAN profile is malformed JSONL") from None
    can_ids = profile.get("can_ids")
    if not isinstance(can_ids, dict) or not can_ids:
        raise ValueError("CAN profile contains no CAN-IDs")
    return profile, profile_raw


def issue_can_artifacts(
    *, profile_uri: str, use_context: bool, context_columns: list[str],
    vehicle_id: str, snaps: Path, root: Path, run_stage: Callable[..., dict],
) -> tuple[dict[str, Any], dict[str, CanDatasetArtifactRef], CanDatasetArtifactRef]:
    """Issue one exact schema per profiled CAN-ID plus one prior-data policy."""
    profile, profile_raw = load_can_profile(profile_uri)
    can_ids = profile["can_ids"]
    source_digest = hashlib.sha256(profile_raw).hexdigest()
    artifacts: dict[str, Any] = {}
    schema_refs: dict[str, CanDatasetArtifactRef] = {}
    for can_id in sorted(map(str, can_ids)):
        role = f"signal_schema:{can_id}"
        result = run_stage(
            role, "recipe://local/can-signal-schema@1", [profile_uri],
            {"can_id": can_id, "source_digests": [source_digest]}, snaps, root,
            f"keystone:{vehicle_id}:signal-schema:{can_id}",
            input_roles=["primary_dataset"],
        )
        if "error" in result:
            raise ValueError(f"signal schema issuance failed for {can_id}: {result['error']}")
        artifacts[role] = result
        schema_refs[can_id] = dataset_artifact_ref(result)
    selected = sorted(set(context_columns or (DEFAULT_PRIOR_CONTEXT if use_context else [])))
    policy = run_stage(
        "prior_policy", "recipe://local/can-prior-policy@1", [],
        {"use_context": use_context, "prior_data_allowlist": selected}, snaps, root,
        f"keystone:{vehicle_id}:prior-policy",
    )
    if "error" in policy:
        raise ValueError(f"prior policy issuance failed: {policy['error']}")
    artifacts["prior_data_policy"] = policy
    return artifacts, schema_refs, dataset_artifact_ref(policy)


def _single_record(raw: bytes) -> dict[str, Any]:
    records = [json.loads(line) for line in raw.splitlines() if line.strip()]
    if len(records) != 1 or not isinstance(records[0], dict):
        raise ValueError("CAN profile must contain exactly one object")
    return records[0]


__all__ = ["DEFAULT_PRIOR_CONTEXT", "issue_can_artifacts", "load_can_profile"]
