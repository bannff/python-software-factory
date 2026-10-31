"""Rehydrate generic time-series jobs from authenticated CAN terminals."""
from __future__ import annotations

from typing import Any

from .can_family_specs import CanFamilySpec, family_spec
from .ports import TimeSeriesTrainingConfig, TimeSeriesTrainingJob


def rehydrate_training_job(
    row: dict[str, Any],
) -> tuple[TimeSeriesTrainingJob, CanFamilySpec, dict[str, dict[str, Any]], dict[str, Any]]:
    """Build the generic port job and exact passport inputs from one sealed row."""
    family = str(row.get("model_family", "lightgbm"))
    spec = family_spec(family)
    refs = row.get("artifact_refs")
    if not isinstance(refs, dict) or set(refs) != spec.required_refs:
        raise ValueError("authenticated training row has incomplete family refs")
    job = TimeSeriesTrainingJob(
        id=str(row["job_id"]), model_type=spec.model_type, status="completed",
        config=TimeSeriesTrainingConfig(**row["training_config"]),
        metrics=dict(row["metrics"]), model_path=str(row["model_path"]),
    )
    info = {
        "n_samples": row["n_samples"], "window_size": row["window_size"],
        "n_features": row["n_features"],
    }
    if spec.timing_ref is not None:
        info["timespans_uri"] = refs[spec.timing_ref]["uri"]
    return job, spec, refs, info


__all__ = ["rehydrate_training_job"]
