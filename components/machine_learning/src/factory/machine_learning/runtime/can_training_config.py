"""Pure per-family configuration and row contracts for CAN training."""
from __future__ import annotations

from typing import Any

from .ports import TimeSeriesModelType, TimeSeriesTrainingConfig


def default_training_config(
    model_type: TimeSeriesModelType, window_size: int,
) -> TimeSeriesTrainingConfig:
    if model_type is TimeSeriesModelType.lightgbm:
        return TimeSeriesTrainingConfig(epochs=1, window_size=window_size)
    if model_type is TimeSeriesModelType.lnn:
        return TimeSeriesTrainingConfig(
            epochs=20, window_size=window_size, learning_rate=5e-4,
        )
    if model_type is TimeSeriesModelType.chronos:
        return TimeSeriesTrainingConfig(
            epochs=10, window_size=window_size, learning_rate=1e-4,
        )
    if model_type is TimeSeriesModelType.patchtst:
        return TimeSeriesTrainingConfig(
            epochs=15, window_size=window_size, learning_rate=1e-4,
        )
    if model_type in (TimeSeriesModelType.lstm, TimeSeriesModelType.tcn):
        return TimeSeriesTrainingConfig(
            epochs=10, window_size=window_size, learning_rate=1e-3,
        )
    raise ValueError(
        f"Model type {model_type.value} is generative and not supported "
        "in the per-CAN-ID classification competition."
    )


def pick_x_uri(model_type: TimeSeriesModelType, info: dict[str, Any]) -> str:
    """Select flattened LightGBM input or the native 3D sequence input."""
    return info["x_2d_uri" if model_type is TimeSeriesModelType.lightgbm else "x_3d_uri"]


def resolve_model_types(
    model_types: list[TimeSeriesModelType] | list[str] | None,
) -> list[TimeSeriesModelType]:
    """Strictly coerce a unique requested classifier family list."""
    if model_types is None:
        return [TimeSeriesModelType.lightgbm]
    resolved: list[TimeSeriesModelType] = []
    for value in model_types:
        try:
            item = value if isinstance(value, TimeSeriesModelType) else TimeSeriesModelType(value)
        except ValueError as exc:
            valid = ", ".join(item.value for item in TimeSeriesModelType)
            raise ValueError(f"Unknown model_type {value!r}. Valid: {valid}") from exc
        if item in resolved:
            raise ValueError(f"Duplicate model_type {item.value!r}")
        resolved.append(item)
    if not resolved:
        raise ValueError("model_types must not be empty")
    return resolved


def build_comparison_row(
    *, rank: int, arb_id: str, info: dict[str, Any], job: Any,
    model_type: TimeSeriesModelType,
) -> dict[str, Any]:
    return {
        "rank": rank, "can_id": arb_id, "model_type": model_type.value,
        "n_windows": info["n_samples"], "n_features": info["n_features"],
        "window_size": info["window_size"], "label_dist": info["label_dist"],
        "metrics": dict(job.metrics), "model_id": job.id, "model_path": job.model_path,
    }


__all__ = [
    "build_comparison_row", "default_training_config", "pick_x_uri",
    "resolve_model_types",
]
