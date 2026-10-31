"""Dataset-owned CAN feature-contract and X/y materialization."""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from numbers import Real
from pathlib import Path
from typing import Any

import numpy as np

from .can_artifact_models import CanArtifactRef, CanPriorDataPolicy, CanSignalSchema
from .can_terminal_canonical import canonical_json
from .can_terminal_paths import checked_output_path
from .can_terminal_publishing import publish_bytes, publish_npy
from .can_terminal_window_validation import validate_window
from .helpers import load_records_from_uri

_EXCLUDED = tuple(sorted({
    "correlation", "correlation_heatmap", "failure_mode", "failure_strategy",
    "failure_timestamp_ns", "is_failure", "label", "provenance",
    "source_lineage", "synthetic_lineage", "target", "timestamp_ns",
}))


def prepare_training_bundle(
    *, augmented_uri: str, augmented_digest: str, policy: CanPriorDataPolicy,
    policy_ref: CanArtifactRef, schemas: dict[str, CanSignalSchema],
    schema_refs: dict[str, CanArtifactRef], root: Path, request_sha256: str,
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    """Validate exact v2 windows and publish per-CAN immutable tensors."""
    records = load_records_from_uri(augmented_uri)
    counts = Counter(str(item.get("can_id", "")) for item in records)
    top_ids = [key for key, _ in sorted(counts.items(), key=lambda item: (-item[1], item[0])) if key]
    if not top_ids:
        raise ValueError("augmented Dataset contains no CAN windows")
    output = checked_output_path(
        root, root / "can_terminal" / "prepared" / request_sha256,
    )
    artifacts: dict[str, dict[str, Any]] = {}
    prepared: dict[str, Any] = {}
    for can_id in top_ids:
        if can_id not in schemas or can_id not in schema_refs:
            raise ValueError(f"signal schema missing CAN-ID {can_id}")
        subset = [item for item in records if str(item.get("can_id")) == can_id]
        contract = _contract(
            subset[0], can_id, augmented_digest, policy, policy_ref,
            schemas[can_id], schema_refs[can_id],
        )
        X, y, timespans = _arrays(subset, contract)
        prefix = hashlib.sha256(can_id.encode()).hexdigest()[:16]
        contract_key = f"feature_contract:{can_id}"
        x3_key, x2_key, y_key = (
            f"prepared_x_3d:{can_id}", f"prepared_x_2d:{can_id}",
            f"prepared_y:{can_id}",
        )
        artifacts[contract_key] = publish_bytes(
            output, f"{prefix}-contract", canonical_json(contract), ".json",
        )
        artifacts[x3_key] = publish_npy(output, f"{prefix}-X-3d", X)
        artifacts[x2_key] = publish_npy(
            output, f"{prefix}-X-2d", X.reshape(len(X), -1),
        )
        artifacts[y_key] = publish_npy(output, f"{prefix}-y", y)
        timespans_key = None
        if timespans is not None:
            timespans_key = f"prepared_timespans:{can_id}"
            artifacts[timespans_key] = publish_npy(
                output, f"{prefix}-timespans", timespans,
            )
        prepared[can_id] = {
            "contract_artifact": contract_key,
            "x_3d_artifact": x3_key,
            "x_2d_artifact": x2_key,
            "y_artifact": y_key,
            "timespans_artifact": timespans_key,
            "n_samples": int(X.shape[0]),
            "window_size": int(X.shape[1]),
            "n_features": int(X.shape[2]),
            "label_dist": {
                "0": int((y == 0).sum()), "1": int((y == 1).sum()),
            },
        }
    return {
        "schema_version": "1.0", "top_can_ids": top_ids,
        "source_digests": [augmented_digest],
        "prior_data_policy_ref": policy_ref.model_dump(mode="json"),
        "signal_schema_refs_by_can_id": {
            key: value.model_dump(mode="json")
            for key, value in sorted(schema_refs.items())
        },
        "prepared_by_can_id": prepared,
    }, artifacts


def _contract(
    first: dict[str, Any], can_id: str, source_digest: str,
    policy: CanPriorDataPolicy, policy_ref: CanArtifactRef,
    schema: CanSignalSchema, schema_ref: CanArtifactRef,
) -> dict[str, Any]:
    signal = tuple(schema.signal_columns)
    context = tuple(policy.prior_data_allowlist)
    timesteps = _positive_int(first, "num_timesteps")
    values: dict[str, Any] = {
        "version": "2.0", "digest": "0" * 64, "can_id": can_id,
        "signal_schema_ref": schema_ref.model_dump(mode="json"),
        "prior_data_policy_ref": policy_ref.model_dump(mode="json"),
        "signal_columns": list(signal), "context_columns": list(context),
        "ordered_columns": [
            *[f"signal:{name}" for name in signal],
            *[f"context:{name}" for name in context],
        ],
        "required_shape": [timesteps, len(signal) + len(context)],
        "required_width": timesteps * (len(signal) + len(context)),
        "tensor_layout": "time_features", "dtype": "float32",
        "fill_policy": {"version": "1.0", "missing_value": 0.0, "non_finite_value": 0.0},
        "window_size_ms": _positive_int(first, "window_size_ms"),
        "step_size_ms": _positive_int(first, "step_size_ms"),
        "grid_resolution_ms": _positive_int(first, "grid_resolution_ms"),
        "observation_cutoff_ms": _positive_int(first, "observation_cutoff_ms"),
        "label_horizon_ms": int(first.get("label_horizon_ms", 0)),
        "num_timesteps": timesteps, "excluded_fields": list(_EXCLUDED),
        "source_digests": sorted({source_digest, policy_ref.digest, schema_ref.digest}),
    }
    body = dict(values)
    body.pop("digest")
    values["digest"] = hashlib.sha256(canonical_json(body)).hexdigest()
    return values


def _arrays(
    records: list[dict[str, Any]], contract: dict[str, Any],
) -> tuple[np.ndarray, np.ndarray, np.ndarray | None]:
    shape = tuple(contract["required_shape"])
    X = np.empty((len(records), *shape), dtype=np.float32)
    y = np.empty((len(records),), dtype=np.int64)
    timing = any("timespans" in item for item in records)
    timespans = np.empty((len(records), shape[0]), dtype=np.float64) if timing else None
    for index, item in enumerate(records):
        validate_window(item, contract, index)
        signal = item["signal"]["values"]
        context = item["context"]["values"]
        X[index] = [[_number(value) for value in (*srow, *crow)]
                    for srow, crow in zip(signal, context, strict=True)]
        y[index] = int(item["label"])
        if timespans is not None:
            values = item.get("timespans", [])
            if not isinstance(values, list) or len(values) != shape[0] or any(
                isinstance(value, bool) or not isinstance(value, Real)
                or not np.isfinite(float(value)) or float(value) <= 0
                for value in values
            ):
                raise ValueError("timespans must be finite positive and match num_timesteps")
            timespans[index] = np.asarray(values, dtype=np.float64)
    return X, y, timespans


def _number(value: Any) -> float:
    if value is None:
        return 0.0
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError("CAN feature values must be numeric")
    result = float(value)
    if np.isfinite(result) and abs(result) > float(np.finfo(np.float32).max):
        raise ValueError("CAN feature value exceeds float32 range")
    return result if np.isfinite(result) else 0.0


def _positive_int(value: dict[str, Any], name: str) -> int:
    result = value.get(name)
    if isinstance(result, bool) or not isinstance(result, int) or result <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return result


__all__ = ["prepare_training_bundle"]
