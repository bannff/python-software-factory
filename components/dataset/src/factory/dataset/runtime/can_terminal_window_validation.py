"""Strict validation of canonical v2 CAN windows before tensorization."""
from __future__ import annotations

from typing import Any


def validate_window(item: dict[str, Any], contract: dict[str, Any], index: int) -> None:
    if item.get("schema_version") != "2.0" or item.get("can_id") != contract["can_id"]:
        raise ValueError(f"window {index} identity does not match feature contract")
    for name in (
        "window_size_ms", "step_size_ms", "grid_resolution_ms",
        "observation_cutoff_ms", "label_horizon_ms", "num_timesteps",
    ):
        observed = item.get(name)
        if isinstance(observed, bool) or observed != contract[name]:
            raise ValueError(f"window {index} {name} does not match feature contract")
    _validate_bounds(item, contract, index)
    metadata = item.get("metadata") or {}
    for name in ("signal_schema_ref", "prior_data_policy_ref"):
        if metadata.get(name) != contract[name]:
            raise ValueError(f"window {index} {name} mismatch")
    for plane, columns in (
        ("signal", contract["signal_columns"]),
        ("context", contract["context_columns"]),
    ):
        value = item.get(plane) or {}
        rows = value.get("values")
        if value.get("columns") != columns or not isinstance(rows, list) \
                or len(rows) != contract["num_timesteps"] \
                or any(not isinstance(row, list) or len(row) != len(columns)
                       for row in rows):
            raise ValueError(f"window {index} {plane} plane mismatch")
    if isinstance(item.get("label"), bool) or item.get("label") not in (0, 1):
        raise ValueError(f"window {index} label is invalid")


def _validate_bounds(item: dict[str, Any], contract: dict[str, Any], index: int) -> None:
    bounds = item.get("bounds")
    if not isinstance(bounds, dict):
        raise ValueError(f"window {index} missing temporal bounds")
    start = bounds.get("window_start_ns")
    cutoff = bounds.get("observation_cutoff_ns")
    end = bounds.get("label_horizon_end_ns")
    if any(isinstance(value, bool) or not isinstance(value, int)
           for value in (start, cutoff, end)):
        raise ValueError(f"window {index} temporal bounds must be integers")
    if cutoff - start != contract["observation_cutoff_ms"] * 1_000_000:
        raise ValueError(f"window {index} observation bounds mismatch")
    if end - cutoff != contract["label_horizon_ms"] * 1_000_000:
        raise ValueError(f"window {index} label bounds mismatch")


__all__ = ["validate_window"]
