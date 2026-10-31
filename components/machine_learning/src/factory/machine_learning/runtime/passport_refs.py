"""Immutable references used by the generic model-passport contract."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .passport_validation import (
    require_digest, require_format, require_media_type, require_text, require_uri,
)


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)


class PassportArtifactRef(FrozenModel):
    role: str
    uri: str
    digest: str
    media_type: str
    format: str
    size_bytes: int = Field(strict=True, ge=0)
    identity: str | None = None
    version: str | None = None

    @field_validator("role")
    @classmethod
    def _role(cls, value: str) -> str:
        return require_format(value)

    @field_validator("uri")
    @classmethod
    def _uri(cls, value: str) -> str:
        return require_uri(value, "artifact URI")

    @field_validator("digest")
    @classmethod
    def _digest(cls, value: str) -> str:
        return require_digest(value, "artifact digest")

    @field_validator("media_type")
    @classmethod
    def _media_type(cls, value: str) -> str:
        return require_media_type(value)

    @field_validator("format")
    @classmethod
    def _format(cls, value: str) -> str:
        return require_format(value)

    @field_validator("identity", "version")
    @classmethod
    def _optional_text(cls, value: str | None) -> str | None:
        return require_text(value, "artifact identity/version") if value is not None else None


class AdapterBinding(FrozenModel):
    adapter: str
    version: str
    config_digest: str

    @field_validator("adapter", "version")
    @classmethod
    def _text(cls, value: str) -> str:
        return require_text(value, "adapter identity/version")

    @field_validator("config_digest")
    @classmethod
    def _config_digest(cls, value: str) -> str:
        return require_digest(value, "adapter config digest")


class PreparationBinding(FrozenModel):
    x: PassportArtifactRef
    y: PassportArtifactRef
    feature_contract: PassportArtifactRef
    x_layout: str
    x_shape: tuple[int, ...] = Field(min_length=1)
    y_shape: tuple[int, ...] = Field(min_length=1)
    contract_shape: tuple[int, ...] = Field(min_length=1)
    contract_width: int = Field(strict=True, gt=0)
    materializer: AdapterBinding
    timespans: PassportArtifactRef | None = None
    timespans_shape: tuple[int, ...] | None = None

    @field_validator("x_layout")
    @classmethod
    def _layout(cls, value: str) -> str:
        return require_format(value)

    @field_validator("x_shape", "y_shape", "contract_shape")
    @classmethod
    def _shape(cls, value: tuple[int, ...]) -> tuple[int, ...]:
        if any(isinstance(item, bool) or item <= 0 for item in value):
            raise ValueError("artifact shapes must contain positive integers")
        return value
    @field_validator("timespans_shape")
    @classmethod
    def _optional_shape(cls, value: tuple[int, ...] | None) -> tuple[int, ...] | None:
        if value is not None and any(isinstance(item, bool) or item <= 0 for item in value):
            raise ValueError("timespans shape must contain positive integers")
        return value
    @model_validator(mode="after")
    def _timing_contract(self) -> "PreparationBinding":
        if (self.timespans is None) != (self.timespans_shape is None):
            raise ValueError("timespans artifact and shape must be declared together")
        if self.timespans is not None and self.timespans.role != "prepared_timespans":
            raise ValueError("timespans artifact role is invalid")
        return self


class ArchitectureBinding(FrozenModel):
    architecture: str
    framework: str
    framework_version: str
    config: dict[str, Any]

    @field_validator("architecture", "framework", "framework_version")
    @classmethod
    def _text(cls, value: str) -> str:
        return require_text(value, "architecture field")


class InferenceBinding(FrozenModel):
    adapter: str
    loader: str
    version: str

    @field_validator("adapter", "loader", "version")
    @classmethod
    def _text(cls, value: str) -> str:
        return require_text(value, "inference identity")


class ScenarioLineageBinding(FrozenModel):
    identity: str
    version: str
    uri: str
    digest: str
    generator_adapter: str
    generator_version: str
    seed: int = Field(strict=True, ge=0, le=2**63 - 1)

    @field_validator("identity", "version", "generator_adapter", "generator_version")
    @classmethod
    def _text(cls, value: str) -> str:
        return require_text(value, "scenario lineage field")

    @field_validator("uri")
    @classmethod
    def _uri(cls, value: str) -> str:
        return require_uri(value, "ScenarioPack URI")

    @field_validator("digest")
    @classmethod
    def _digest(cls, value: str) -> str:
        return require_digest(value, "ScenarioPack digest")


class PassportPredecessorRef(FrozenModel):
    model_id: str
    model_version: str
    passport_revision: int = Field(strict=True, gt=0)
    uri: str
    digest: str

    @field_validator("model_id", "model_version")
    @classmethod
    def _identity(cls, value: str) -> str:
        return require_text(value, "predecessor model identity/version")

    @field_validator("uri")
    @classmethod
    def _uri(cls, value: str) -> str:
        return require_uri(value, "predecessor URI")

    @field_validator("digest")
    @classmethod
    def _digest(cls, value: str) -> str:
        return require_digest(value, "predecessor digest")


__all__ = [
    "AdapterBinding", "ArchitectureBinding", "FrozenModel", "InferenceBinding",
    "PassportArtifactRef", "PassportPredecessorRef", "PreparationBinding",
    "ScenarioLineageBinding",
]
