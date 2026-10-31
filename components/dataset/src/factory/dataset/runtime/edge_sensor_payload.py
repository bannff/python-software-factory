"""Typed JSON payloads and horizon checks for edge sensor windows."""
from __future__ import annotations

import math
from itertools import pairwise
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .edge_sensor_contracts import EdgeSensorWindowRecord

EdgeSensorModality = Literal[
    "accelerometer", "gyroscope", "imu", "audio", "image",
    "environmental", "can", "other",
]


class EdgeSensorSample(BaseModel):
    """One timestamped row, with values aligned to payload channel order."""

    model_config = ConfigDict(extra="forbid", strict=True)

    timestamp_ms: int = Field(ge=0)
    values: list[int | float] = Field(min_length=1)

    @field_validator("values")
    @classmethod
    def _finite_values(cls, values: list[int | float]) -> list[int | float]:
        if any(not math.isfinite(float(value)) for value in values):
            raise ValueError("Sensor sample values must be finite")
        return values


class EdgeSensorWindowPayload(BaseModel):
    """Versioned, ordered sensor values stored behind an input reference."""

    model_config = ConfigDict(extra="forbid", strict=True)

    schema_version: Literal["1.0"]
    modality: EdgeSensorModality
    channels: list[str] = Field(min_length=1)
    samples: list[EdgeSensorSample] = Field(min_length=1)

    @field_validator("channels")
    @classmethod
    def _unique_channels(cls, channels: list[str]) -> list[str]:
        cleaned = [channel.strip() for channel in channels]
        if any(not channel for channel in cleaned):
            raise ValueError("Sensor channel names must be non-empty")
        if len(cleaned) != len(set(cleaned)):
            raise ValueError("Sensor channel names must be unique")
        return cleaned

    @model_validator(mode="after")
    def _validate_rows_and_order(self) -> EdgeSensorWindowPayload:
        timestamps = [sample.timestamp_ms for sample in self.samples]
        if any(later <= earlier for earlier, later in pairwise(timestamps)):
            raise ValueError("Sensor sample timestamps must be strictly increasing")
        for index, sample in enumerate(self.samples):
            if len(sample.values) != len(self.channels):
                raise ValueError(
                    f"Sensor sample {index} has {len(sample.values)} values for "
                    f"{len(self.channels)} channels"
                )
        return self


def validate_edge_sensor_payload(
    content: bytes, record: EdgeSensorWindowRecord,
) -> EdgeSensorWindowPayload:
    """Parse payload JSON and enforce modality and observed/future boundaries."""
    try:
        payload = EdgeSensorWindowPayload.model_validate_json(content)
    except Exception as error:
        raise ValueError("Sensor payload violates the versioned shape/time contract") from error
    if payload.modality != record.modality:
        raise ValueError("Sensor payload modality does not match its record")
    if payload.samples[-1].timestamp_ms != record.observed_through_ms:
        raise ValueError("Observed-through timestamp does not match the final sample")
    if record.label_start_ms <= payload.samples[-1].timestamp_ms:
        raise ValueError("Label horizon must start after the final observed sample")
    if record.label_end_ms < record.label_start_ms:
        raise ValueError("Label horizon end must not precede its start")
    return payload
