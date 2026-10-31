"""Strict contract for hash-bound edge-model evaluation evidence."""
from __future__ import annotations

from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    FiniteFloat,
    StringConstraints,
    ValidationError,
    field_validator,
    model_validator,
)

_Digest = Annotated[str, StringConstraints(pattern=r"^sha256:[0-9a-f]{64}$")]
_Identity = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=256)]
_MetricName = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_.-]{0,63}$")]
_Unit = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=32)]


class _EvidenceModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class ModelDigest(_EvidenceModel):
    id: _Identity
    digest: _Digest


class DatasetSplitDigest(_EvidenceModel):
    name: _Identity
    digest: _Digest


class DatasetDigest(_EvidenceModel):
    id: _Identity
    digest: _Digest
    split: DatasetSplitDigest


class EvaluatorDigest(_EvidenceModel):
    id: _Identity
    version: _Identity
    digest: _Digest


class PolicyDigest(_EvidenceModel):
    id: _Identity
    digest: _Digest


class EdgeTarget(_EvidenceModel):
    platform: Literal["ios", "android", "linux", "windows", "macos"]
    device_class: Literal["phone", "tablet", "wearable", "sbc", "edge_server"]
    device_model: _Identity
    fidelity: Literal["native_device", "native_simulator", "emulated", "container_proxy"]


class EdgeRuntime(_EvidenceModel):
    name: _Identity
    version: _Identity
    backend: _Identity


class EdgeMetric(_EvidenceModel):
    name: _MetricName
    category: Literal["task", "resource"]
    value: FiniteFloat
    unit: _Unit


class UnavailableMeasurement(_EvidenceModel):
    name: _MetricName
    category: Literal["task", "resource"]
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=512)]


class EdgeModelEvidence(_EvidenceModel):
    """Reproducibility facts; raw examples and model inputs belong in artifacts."""

    schema_version: Literal[1]
    model: ModelDigest
    dataset: DatasetDigest
    evaluator: EvaluatorDigest
    policy: PolicyDigest
    target: EdgeTarget
    runtime: EdgeRuntime
    metrics: tuple[EdgeMetric, ...]
    unavailable_measurements: tuple[UnavailableMeasurement, ...]

    @field_validator("metrics", "unavailable_measurements", mode="before")
    @classmethod
    def freeze_json_arrays(cls, value: object) -> object:
        """Accept JSON arrays, but detach them into immutable validated tuples."""
        return tuple(value) if isinstance(value, list) else value

    @model_validator(mode="after")
    def validate_measurement_coverage(self) -> EdgeModelEvidence:
        measured = {(item.category, item.name) for item in self.metrics}
        unavailable = {(item.category, item.name) for item in self.unavailable_measurements}
        if len(measured) != len(self.metrics):
            raise ValueError("metrics must have unique category/name pairs")
        if len(unavailable) != len(self.unavailable_measurements):
            raise ValueError("unavailable_measurements must have unique category/name pairs")
        if measured & unavailable:
            raise ValueError("a measurement cannot be both available and unavailable")
        covered_categories = {category for category, _ in measured | unavailable}
        if covered_categories != {"task", "resource"}:
            raise ValueError(
                "task and resource measurements must be recorded or explicitly unavailable"
            )
        return self


def validation_reason(error: ValidationError) -> str:
    """Describe the first invalid boundary field without echoing supplied values."""
    first = error.errors(include_url=False)[0]
    context_error = first.get("ctx", {}).get("error")
    if context_error is not None:
        return str(context_error)
    location = ".".join(str(part) for part in first["loc"]) or "evidence"
    return f"{location} ({first['type']})"
