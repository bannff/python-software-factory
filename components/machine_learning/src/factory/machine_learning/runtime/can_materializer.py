"""Strict two-pass tensor materialization shared by CAN training and inference."""
from __future__ import annotations

from dataclasses import dataclass
from numbers import Real
from typing import Any

import numpy as np

from .can_feature_contract import CanFeatureContract


@dataclass(frozen=True)
class CanMaterializedBatch:
    X: np.ndarray
    y: np.ndarray
    metadata: tuple[dict[str, Any], ...]


def materialize_can_windows(
    windows: list[dict[str, Any]], contract: CanFeatureContract, *, flatten: bool = False,
) -> CanMaterializedBatch:
    """Validate every window before allocating the output tensor."""
    if not windows:
        raise ValueError("No records provided to materialize")
    validated = [_validate_window(window, contract, index) for index, window in enumerate(windows)]
    shape = (len(windows), *contract.required_shape)
    X = np.empty(shape, dtype=np.dtype(contract.dtype))
    y = np.empty((len(windows),), dtype=np.int64)
    metadata: list[dict[str, Any]] = []
    for index, (values, label, item_metadata) in enumerate(validated):
        X[index] = values
        y[index] = label
        metadata.append(item_metadata)
    if flatten:
        X = X.reshape(len(windows), contract.required_width)
    return CanMaterializedBatch(X=X, y=y, metadata=tuple(metadata))


def _validate_window(
    window: dict[str, Any], contract: CanFeatureContract, index: int,
) -> tuple[list[list[float]], int, dict[str, Any]]:
    if window.get("schema_version") != "2.0":
        raise ValueError(f"window {index} has unsupported schema_version")
    can_id = window.get("can_id")
    if can_id != contract.can_id:
        raise ValueError(f"window {index} CAN-ID mismatch: {can_id!r}")
    _validate_temporal(window, contract, index)
    _validate_artifact_refs(window, contract, index)
    signal = _plane(window, "signal", contract.signal_columns, index)
    context = _plane(window, "context", contract.context_columns, index)
    values: list[list[float]] = []
    for timestep in range(contract.num_timesteps):
        values.append([
            _numeric(raw, contract, index, timestep)
            for raw in (*signal[timestep], *context[timestep])
        ])
    label = window.get("label")
    if isinstance(label, bool) or label not in (0, 1):
        raise ValueError(f"window {index} has invalid or missing label")
    metadata = {
        "can_id": can_id,
        "bounds": window["bounds"],
        "provenance": window.get("provenance", {}),
    }
    return values, int(label), metadata


def _validate_temporal(
    window: dict[str, Any], contract: CanFeatureContract, index: int,
) -> None:
    expected = {
        "window_size_ms": contract.window_size_ms,
        "step_size_ms": contract.step_size_ms,
        "grid_resolution_ms": contract.grid_resolution_ms,
        "observation_cutoff_ms": contract.observation_cutoff_ms,
        "label_horizon_ms": contract.label_horizon_ms,
        "num_timesteps": contract.num_timesteps,
    }
    for name, value in expected.items():
        observed = window.get(name)
        if isinstance(observed, bool) or not isinstance(observed, int) or observed != value:
            raise ValueError(f"window {index} {name} does not match contract")
    bounds = window.get("bounds")
    if not isinstance(bounds, dict):
        raise ValueError(f"window {index} missing bounds")
    start, cutoff, end = (
        bounds.get("window_start_ns"), bounds.get("observation_cutoff_ns"),
        bounds.get("label_horizon_end_ns"),
    )
    if any(isinstance(v, bool) or not isinstance(v, int) for v in (start, cutoff, end)):
        raise ValueError(f"window {index} bounds must be integer nanoseconds")
    if cutoff - start != contract.observation_cutoff_ms * 1_000_000:
        raise ValueError(f"window {index} observation bounds do not match contract")
    if end - cutoff != contract.label_horizon_ms * 1_000_000:
        raise ValueError(f"window {index} label bounds do not match contract")


def _validate_artifact_refs(
    window: dict[str, Any], contract: CanFeatureContract, index: int,
) -> None:
    metadata = window.get("metadata")
    if not isinstance(metadata, dict):
        raise ValueError(f"window {index} missing artifact-ref metadata")
    expected = {
        "signal_schema_ref": contract.signal_schema_ref.model_dump(mode="json"),
        "prior_data_policy_ref": contract.prior_data_policy_ref.model_dump(mode="json"),
    }
    for name, value in expected.items():
        if metadata.get(name) != value:
            raise ValueError(f"window {index} {name} does not match contract")


def _plane(
    window: dict[str, Any], name: str, columns: tuple[str, ...], index: int,
) -> list[list[Any]]:
    plane = window.get(name)
    if not isinstance(plane, dict) or plane.get("columns") != list(columns):
        raise ValueError(f"window {index} {name} columns do not match contract")
    values = plane.get("values")
    if not isinstance(values, list) or len(values) != window["num_timesteps"]:
        raise ValueError(f"window {index} {name} timestep count is inconsistent")
    for row in values:
        if not isinstance(row, list) or len(row) != len(columns):
            raise ValueError(f"window {index} {name} row width is inconsistent")
    return values


def _numeric(raw: Any, contract: CanFeatureContract, window: int, timestep: int) -> float:
    if raw is None:
        return float(contract.fill_policy.missing_value)
    if isinstance(raw, bool) or not isinstance(raw, Real):
        raise ValueError(f"non-numeric value at window {window}, timestep {timestep}")
    value = float(raw)
    if not np.isfinite(value):
        return float(contract.fill_policy.non_finite_value)
    if abs(value) > np.finfo(np.float32).max:
        raise ValueError(f"value exceeds float32 domain at window {window}, timestep {timestep}")
    return value


__all__ = ["CanMaterializedBatch", "materialize_can_windows"]
