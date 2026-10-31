"""Strict server-assembled Dataset legacy binding carried by CAN passports."""
from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)


class LegacyJob(_Frozen):
    job_id: str

    @field_validator("job_id")
    @classmethod
    def _job_id(cls, value: str) -> str:
        if not value or value != value.strip():
            raise ValueError("legacy job identity must be non-empty and trimmed")
        return value


class LegacyIngest(LegacyJob):
    n_mf4: int = Field(strict=True, ge=0)


class LegacyContractArtifact(LegacyJob):
    uri: str
    digest: str

    @field_validator("uri")
    @classmethod
    def _uri(cls, value: str) -> str:
        if not value.startswith("file://"):
            raise ValueError("legacy contract artifact must use a file URI")
        return value

    @field_validator("digest")
    @classmethod
    def _digest(cls, value: str) -> str:
        if re.fullmatch(r"[0-9a-f]{64}", value) is None:
            raise ValueError("legacy contract artifact digest must be SHA-256")
        return value


class LegacyProjection(_Frozen):
    ingest: LegacyIngest
    profile: LegacyJob
    contract_artifacts: dict[str, LegacyContractArtifact]
    synthesize: LegacyJob
    window: LegacyJob
    augment: LegacyJob
    top_can_ids: tuple[str, ...] = Field(min_length=1)
    context: dict[str, str] | None = None
    context_artifacts: dict[str, str] | None = None

    @field_validator("top_can_ids", mode="before")
    @classmethod
    def _tuple_ids(cls, value: Any) -> tuple[str, ...]:
        return tuple(value or ())

    @model_validator(mode="after")
    def _context_pair(self) -> "LegacyProjection":
        if (self.context is None) != (self.context_artifacts is None):
            raise ValueError("legacy context and context_artifacts must be paired")
        return self


class CanLegacyBinding(_Frozen):
    """Per-model rank plus exact trusted Dataset-stage projection."""

    vehicle_id: str
    can_id: str
    rank: int = Field(strict=True, gt=0)
    n_windows: int = Field(strict=True, gt=0)
    n_features: int = Field(strict=True, gt=0)
    window_size: int = Field(strict=True, gt=0)
    label_dist: dict[str, int]
    dataset_projection: LegacyProjection

    @field_validator("vehicle_id", "can_id")
    @classmethod
    def _text(cls, value: str) -> str:
        if not value or value != value.strip():
            raise ValueError("CAN legacy binding identities must be non-empty")
        return value

    @model_validator(mode="after")
    def _membership(self) -> "CanLegacyBinding":
        ids = self.dataset_projection.top_can_ids
        if ids and self.can_id not in ids:
            raise ValueError("passport CAN-ID is absent from Dataset top_can_ids")
        if not self.label_dist or any(
            not key or key != key.strip() or count < 0
            for key, count in self.label_dist.items()
        ):
            raise ValueError("CAN legacy label distribution is invalid")
        if sum(self.label_dist.values()) != self.n_windows:
            raise ValueError("CAN legacy label distribution disagrees with window count")
        return self


def build_can_legacy_binding(
    terminal: dict[str, Any], *, can_id: str, rank: int, row: dict[str, Any],
) -> CanLegacyBinding:
    """Assemble only from trusted Dataset and ML training terminals."""
    return CanLegacyBinding.model_validate({
        "vehicle_id": terminal.get("vehicle_id"), "can_id": can_id, "rank": rank,
        "n_windows": row.get("n_samples"), "n_features": row.get("n_features"),
        "window_size": row.get("window_size"), "label_dist": row.get("label_dist"),
        "dataset_projection": terminal.get("legacy_projection"),
    })


__all__ = [
    "CanLegacyBinding", "LegacyContractArtifact", "LegacyIngest", "LegacyJob",
    "LegacyProjection", "build_can_legacy_binding",
]
