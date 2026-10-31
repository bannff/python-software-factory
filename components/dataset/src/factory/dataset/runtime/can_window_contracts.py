"""Versioned payloads for leakage-safe CAN observation windows."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_FORBIDDEN_CONTEXT_MARKERS = (
    "correlation", "failure", "future", "label", "lineage", "outcome",
    "provenance", "target", "timestamp",
)


class _FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class CanContextFeaturePolicy(_FrozenModel):
    """Versioned declaration permitting only prior-data context in X."""

    version: Literal["1.0"] = "1.0"
    use_context: bool = False
    prior_data_allowlist: tuple[str, ...] = ()

    @field_validator("prior_data_allowlist", mode="before")
    @classmethod
    def _normalize_allowlist(cls, value: Any) -> tuple[str, ...]:
        return tuple(sorted(set(value or ())))

    @model_validator(mode="after")
    def _safe_prior_fields(self) -> "CanContextFeaturePolicy":
        if not self.use_context and self.prior_data_allowlist:
            raise ValueError("disabled context policy requires an empty allowlist")
        forbidden = [
            name for name in self.prior_data_allowlist
            if any(marker in name.lower() for marker in _FORBIDDEN_CONTEXT_MARKERS)
        ]
        if forbidden:
            raise ValueError(f"context policy contains non-prior fields: {forbidden}")
        return self


class CanFeaturePlane(_FrozenModel):
    """Ordered transport plane; values retain the observation grid."""

    columns: tuple[str, ...] = ()
    values: tuple[tuple[Any, ...], ...] = ()

    @model_validator(mode="after")
    def _rectangular(self) -> "CanFeaturePlane":
        if len(set(self.columns)) != len(self.columns):
            raise ValueError("feature plane columns must be unique")
        for row in self.values:
            if len(row) != len(self.columns):
                raise ValueError("feature plane row width does not match columns")
        return self


class CanWindowBounds(_FrozenModel):
    """Half-open observation and label intervals in nanoseconds."""

    window_start_ns: int
    observation_cutoff_ns: int
    label_horizon_end_ns: int

    @model_validator(mode="after")
    def _ordered(self) -> "CanWindowBounds":
        if not self.window_start_ns < self.observation_cutoff_ns:
            raise ValueError("observation cutoff must follow window start")
        if self.label_horizon_end_ns < self.observation_cutoff_ns:
            raise ValueError("label horizon end precedes observation cutoff")
        return self


class CanProvenancePlane(_FrozenModel):
    """Transport-only source, synthetic, and context-observation lineage."""

    source_records: tuple[dict[str, Any], ...] = ()
    synthetic_lineage: tuple[dict[str, Any], ...] = ()
    context_observations: tuple[dict[str, Any], ...] = ()


class CanWindowRecord(_FrozenModel):
    """Canonical Dataset-owned CAN window payload."""

    schema_version: Literal["2.0"] = "2.0"
    can_id: str
    vehicle_id: str
    signal: CanFeaturePlane
    context: CanFeaturePlane = Field(default_factory=CanFeaturePlane)
    provenance: CanProvenancePlane = Field(default_factory=CanProvenancePlane)
    bounds: CanWindowBounds
    label: int = Field(ge=0, le=1)
    window_size_ms: int = Field(gt=0)
    step_size_ms: int = Field(gt=0)
    grid_resolution_ms: int = Field(gt=0)
    observation_cutoff_ms: int = Field(gt=0)
    label_horizon_ms: int = Field(ge=0)
    num_timesteps: int = Field(gt=0)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _grid_matches(self) -> "CanWindowRecord":
        if len(self.signal.values) != self.num_timesteps:
            raise ValueError("signal plane does not match num_timesteps")
        if len(self.context.values) != self.num_timesteps:
            raise ValueError("context plane does not match num_timesteps")
        expected = self.observation_cutoff_ms // self.grid_resolution_ms
        if expected != self.num_timesteps:
            raise ValueError("observation grid does not match num_timesteps")
        return self

    def serialized(self) -> dict[str, Any]:
        """Return v2 planes plus legacy signal-only keys."""
        data = self.model_dump(mode="json")
        signal_values = [list(row) for row in self.signal.values]
        data.update({
            "window_data": signal_values,
            "signal_names": list(self.signal.columns),
            "context_names": list(self.context.columns),
            "context_data": [list(row) for row in self.context.values],
            "arbitration_id": self.can_id,
            "window_start_ns": self.bounds.window_start_ns,
            "observation_cutoff_ns": self.bounds.observation_cutoff_ns,
            "window_end_ns": self.bounds.label_horizon_end_ns,
            "num_features": len(self.signal.columns),
        })
        return data


__all__ = [
    "CanContextFeaturePolicy", "CanFeaturePlane", "CanProvenancePlane",
    "CanWindowBounds", "CanWindowRecord",
]
