"""Exact Dataset-owned CAN authorization artifact bodies."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, StrictInt, field_validator, model_validator


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class CanArtifactRef(_Frozen):
    """Content-addressed identity carried across the Dataset boundary."""

    uri: str
    version: str
    digest: str

    @field_validator("uri", "version")
    @classmethod
    def _text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("artifact reference fields must be non-empty")
        return value

    @field_validator("digest")
    @classmethod
    def _digest(cls, value: str) -> str:
        return _sha256(value, "artifact reference")


class _ArtifactBody(_Frozen):
    version: Literal["1.0"] = "1.0"
    digest: str
    source_digests: tuple[str, ...] = ()

    @field_validator("digest")
    @classmethod
    def _body_digest(cls, value: str) -> str:
        return _sha256(value, "artifact")

    @field_validator("source_digests", mode="before")
    @classmethod
    def _sources(cls, value: Any) -> tuple[str, ...]:
        sources = tuple(value or ())
        if any(not isinstance(item, str) for item in sources):
            raise ValueError("source_digests must contain strings")
        normalized = tuple(sorted(set(sources)))
        for digest in normalized:
            _sha256(digest, "source")
        return normalized


class CanPriorDataPolicy(_ArtifactBody):
    """Exact CanPriorDataPolicy v1.0 body."""

    use_context: bool
    prior_data_allowlist: tuple[str, ...] = ()

    @field_validator("prior_data_allowlist", mode="before")
    @classmethod
    def _allowlist(cls, value: Any) -> tuple[str, ...]:
        columns = tuple(value or ())
        if any(not isinstance(item, str) or not item.strip() for item in columns):
            raise ValueError("prior_data_allowlist entries must be non-empty strings")
        if len(set(columns)) != len(columns):
            raise ValueError("prior_data_allowlist entries must be unique")
        return columns

    @model_validator(mode="after")
    def _policy(self) -> "CanPriorDataPolicy":
        if not self.use_context and self.prior_data_allowlist:
            raise ValueError("disabled prior-data policy must have an empty allowlist")
        return self


class CanSignalSchema(_ArtifactBody):
    """Exact single-CAN CanSignalSchema v1.0 body."""

    can_id: str
    signal_columns: tuple[str, ...]

    @field_validator("can_id")
    @classmethod
    def _can_id(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("signal schema can_id must be non-empty")
        return value

    @field_validator("signal_columns", mode="before")
    @classmethod
    def _columns(cls, value: Any) -> tuple[str, ...]:
        columns = tuple(value or ())
        if not columns or any(
            not isinstance(item, str) or not item.strip() for item in columns
        ):
            raise ValueError("signal_columns must contain non-empty strings")
        if len(set(columns)) != len(columns):
            raise ValueError("signal_columns must be unique")
        return columns


class CanContextObservationProvenance(_Frozen):
    """Proof that selected context was observed and available before a frame."""

    version: Literal["2.0"] = "2.0"
    source_kind: Literal["prior_data"] = "prior_data"
    observed_at_ns: StrictInt
    available_at_ns: StrictInt
    merge_strategy: str

    @model_validator(mode="after")
    def _ordered(self) -> "CanContextObservationProvenance":
        if self.observed_at_ns > self.available_at_ns:
            raise ValueError("context observation is not prior data")
        return self


def _sha256(value: str, label: str) -> str:
    if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise ValueError(f"{label} digest must be lowercase SHA-256")
    return value


__all__ = [
    "CanArtifactRef", "CanContextObservationProvenance",
    "CanPriorDataPolicy", "CanSignalSchema",
]
