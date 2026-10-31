"""Versioned records for leakage-safe edge sensor-window experiments."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .base import _normalize_digest, _require_non_empty


class EdgeSensorInputRef(BaseModel):
    """Content-addressed reference to one immutable sensor-window payload."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    uri: str
    sha256: str

    @field_validator("uri")
    @classmethod
    def _validate_uri(cls, value: str) -> str:
        return _require_non_empty(value, "Edge sensor input URI")

    @field_validator("sha256")
    @classmethod
    def _validate_digest(cls, value: str) -> str:
        return _normalize_digest(value, "edge sensor input")


class EdgeSensorWindowRecord(BaseModel):
    """A labeled sensor window assigned to exactly one group-safe split."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    schema_version: Literal["1.0"]
    record_id: str
    task: str
    modality: Literal[
        "accelerometer", "gyroscope", "imu", "audio", "image",
        "environmental", "can", "other",
    ]
    input_ref: EdgeSensorInputRef
    label: str
    label_provenance: EdgeSensorLabelProvenance
    group_id: str = Field(
        description="Subject, device, or session identity kept wholly within one split.",
    )
    split: Literal["train", "validation", "test"]
    observed_through_ms: int
    label_start_ms: int
    label_end_ms: int

    @field_validator("record_id", "task", "label", "group_id")
    @classmethod
    def _validate_required_text(cls, value: str) -> str:
        return _require_non_empty(value, "Edge sensor record field")

    @field_validator("observed_through_ms", "label_start_ms", "label_end_ms")
    @classmethod
    def _validate_timestamp(cls, value: int) -> int:
        if value < 0:
            raise ValueError("Edge sensor timestamps must be non-negative milliseconds")
        return value

    @field_validator("label_end_ms")
    @classmethod
    def _validate_future_label_horizon(cls, value: int, info) -> int:
        observed_through = info.data.get("observed_through_ms")
        label_start = info.data.get("label_start_ms")
        if observed_through is not None and label_start is not None:
            if label_start <= observed_through:
                raise ValueError("Label horizon must start after observed data ends")
            if value < label_start:
                raise ValueError("Label horizon end must not precede its start")
        return value


class EdgeSensorLabelProvenance(BaseModel):
    """Where a future-window label came from."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    method: Literal["human_annotation", "event_log", "derived_rule"]
    source: str

    @field_validator("source")
    @classmethod
    def _validate_source(cls, value: str) -> str:
        return _require_non_empty(value, "Edge sensor label source")
