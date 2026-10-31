"""Frozen model for exact Dataset-artifact-bound CAN tensors."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .can_artifact_refs import CanDatasetArtifactRef


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class CanFillPolicy(_Frozen):
    version: Literal["1.0"] = "1.0"
    missing_value: float = 0.0
    non_finite_value: float = 0.0


class CanFeatureContract(_Frozen):
    """Exact feature projection and shape bound to two Dataset artifacts."""

    version: Literal["2.0"] = "2.0"
    digest: str
    can_id: str
    signal_schema_ref: CanDatasetArtifactRef
    prior_data_policy_ref: CanDatasetArtifactRef
    signal_columns: tuple[str, ...]
    context_columns: tuple[str, ...] = ()
    ordered_columns: tuple[str, ...]
    required_shape: tuple[int, int]
    required_width: int = Field(gt=0)
    tensor_layout: Literal["time_features"] = "time_features"
    dtype: Literal["float32"] = "float32"
    fill_policy: CanFillPolicy = Field(default_factory=CanFillPolicy)
    window_size_ms: int = Field(gt=0)
    step_size_ms: int = Field(gt=0)
    grid_resolution_ms: int = Field(gt=0)
    observation_cutoff_ms: int = Field(gt=0)
    label_horizon_ms: int = Field(ge=0)
    num_timesteps: int = Field(gt=0)
    excluded_fields: tuple[str, ...] = ()
    source_digests: tuple[str, ...] = ()

    @field_validator("excluded_fields", "source_digests", mode="before")
    @classmethod
    def _sort_unordered(cls, value: Any) -> tuple[str, ...]:
        return tuple(sorted(set(value or ())))

    @model_validator(mode="after")
    def _invariants(self) -> "CanFeatureContract":
        if not self.can_id or not self.signal_columns:
            raise ValueError("contract requires CAN-ID and signal columns")
        if len(set(self.signal_columns)) != len(self.signal_columns) \
                or len(set(self.context_columns)) != len(self.context_columns):
            raise ValueError("feature columns must be unique")
        ordered = tuple(
            [f"signal:{name}" for name in self.signal_columns]
            + [f"context:{name}" for name in self.context_columns]
        )
        if self.ordered_columns != ordered:
            raise ValueError("ordered_columns must match namespaced projections")
        if self.observation_cutoff_ms % self.grid_resolution_ms:
            raise ValueError("observation cutoff must divide the grid")
        if self.num_timesteps != self.observation_cutoff_ms // self.grid_resolution_ms:
            raise ValueError("num_timesteps does not match the observation grid")
        expected_shape = (self.num_timesteps, len(self.ordered_columns))
        if self.required_shape != expected_shape:
            raise ValueError("required_shape does not match the feature projection")
        if self.required_width != expected_shape[0] * expected_shape[1]:
            raise ValueError("required_width must be the flattened LightGBM width")
        for value in (*self.source_digests, self.digest):
            if len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
                raise ValueError("contract digests must be lowercase SHA-256")
        return self


__all__ = ["CanFeatureContract", "CanFillPolicy"]
