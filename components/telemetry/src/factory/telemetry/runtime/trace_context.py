"""Strict validation and typed results for W3C trace context carriers."""
from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_TRACEPARENT = re.compile(
    r"^(?P<version>[0-9a-f]{2})-(?P<trace>[0-9a-f]{32})-"
    r"(?P<span>[0-9a-f]{16})-(?P<flags>[0-9a-f]{2})$"
)
_SUPPORTED_TRACEPARENT_VERSIONS = frozenset({"00"})
_TRACESTATE_KEY = re.compile(r"^[a-z0-9][a-z0-9_*/@-]{0,255}$")


class TraceContextModel(BaseModel):
    """Validated, non-interchangeable W3C identifiers and carrier."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    traceparent: str = Field(
        pattern=r"^[0-9a-f]{2}-[0-9a-f]{32}-[0-9a-f]{16}-[0-9a-f]{2}$",
    )
    traceparent_version: str = Field(pattern=r"^[0-9a-f]{2}$")
    trace_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    span_id: str = Field(pattern=r"^[0-9a-f]{16}$")
    trace_flags: int = Field(ge=0, le=255)
    tracestate: str | None = None
    carrier: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_consistency(self) -> Self:
        match = _TRACEPARENT.fullmatch(self.traceparent)
        if match is None or match.group("version") == "ff":
            raise ValueError("malformed traceparent")
        version = match.group("version")
        if version not in _SUPPORTED_TRACEPARENT_VERSIONS:
            raise ValueError(f"unsupported traceparent version: {version}")
        trace_id = match.group("trace")
        span_id = match.group("span")
        if not int(trace_id, 16) or not int(span_id, 16):
            raise ValueError("traceparent identifiers must not be all zero")
        if self.traceparent_version != version:
            raise ValueError("traceparent_version does not match traceparent")
        if self.trace_id != trace_id:
            raise ValueError("trace_id does not match traceparent")
        if self.span_id != span_id:
            raise ValueError("span_id does not match traceparent")
        if self.trace_flags != int(match.group("flags"), 16):
            raise ValueError("trace_flags does not match traceparent")
        if self.tracestate is not None:
            validate_tracestate(self.tracestate)
        for key, item in self.carrier.items():
            lowered = key.lower()
            if lowered == "traceparent" and item != self.traceparent:
                raise ValueError("carrier traceparent does not match traceparent")
            if lowered == "tracestate":
                validate_tracestate(item)
                if item != self.tracestate:
                    raise ValueError("carrier tracestate does not match tracestate")
        return self

    @property
    def version(self) -> str:
        """Expose the traceparent component with the standard short name."""
        return self.traceparent_version

    @field_validator("carrier")
    @classmethod
    def validate_carrier_values(cls, value: dict[str, str]) -> dict[str, str]:
        seen: set[str] = set()
        for key, item in value.items():
            if not isinstance(key, str) or not isinstance(item, str):
                raise ValueError("W3C carrier keys and values must be strings")
            lowered = key.lower()
            if lowered in {"traceparent", "tracestate"}:
                if lowered in seen:
                    raise ValueError("duplicate W3C context")
                seen.add(lowered)
        return dict(value)


class TraceContextOutput(BaseModel):
    """Typed result for injection and extraction operations."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    ok: bool
    outcome: Literal["injected", "extracted", "rejected", "no_context"]
    carrier: dict[str, str] | None = None
    traceparent: str | None = None
    traceparent_version: str | None = None
    trace_id: str | None = None
    span_id: str | None = None
    trace_flags: int | None = None
    tracestate: str | None = None
    error: str | None = None


def validate_traceparent(value: object) -> TraceContextModel:
    """Validate a supported W3C traceparent without accepting a new-root forgery."""
    if not isinstance(value, str):
        raise ValueError("traceparent must be a string")
    match = _TRACEPARENT.fullmatch(value)
    if match is None or match.group("version") == "ff":
        raise ValueError("malformed traceparent")
    version = match.group("version")
    if version not in _SUPPORTED_TRACEPARENT_VERSIONS:
        raise ValueError(f"unsupported traceparent version: {version}")
    trace_id = match.group("trace")
    span_id = match.group("span")
    if not int(trace_id, 16) or not int(span_id, 16):
        raise ValueError("traceparent identifiers must not be all zero")
    return TraceContextModel(
        traceparent=value,
        traceparent_version=version,
        trace_id=trace_id,
        span_id=span_id,
        trace_flags=int(match.group("flags"), 16),
        carrier={"traceparent": value},
    )


def validate_tracestate(value: object) -> str:
    """Validate and return tracestate byte-for-byte for propagation."""
    if not isinstance(value, str) or not value or len(value) > 512:
        raise ValueError("malformed tracestate")
    members = value.split(",")
    if len(members) > 32:
        raise ValueError("malformed tracestate")
    keys: set[str] = set()
    for member in members:
        item = member.strip()
        if "=" not in item:
            raise ValueError("malformed tracestate")
        key, state_value = item.split("=", 1)
        if key in keys or not _TRACESTATE_KEY.fullmatch(key) or not state_value:
            raise ValueError("malformed tracestate")
        keys.add(key)
        if len(state_value) > 256 or any(
            ord(char) < 0x20 or ord(char) > 0x7e for char in state_value
        ):
            raise ValueError("malformed tracestate")
    return value


def validate_w3c_carrier(value: object) -> TraceContextModel:
    """Validate a carrier and retain its exact header spelling and bytes."""
    if isinstance(value, TraceContextModel):
        return value
    if not isinstance(value, Mapping):
        raise ValueError("W3C carrier must be a mapping")
    carrier = dict(value)
    traceparent: str | None = None
    tracestate: str | None = None
    seen: set[str] = set()
    for key, item in carrier.items():
        if not isinstance(key, str) or not isinstance(item, str):
            raise ValueError("W3C carrier keys and values must be strings")
        lowered = key.lower()
        if lowered not in {"traceparent", "tracestate"}:
            continue
        if lowered in seen:
            raise ValueError("duplicate W3C context")
        seen.add(lowered)
        if lowered == "traceparent":
            traceparent = item
        else:
            tracestate = item
    if traceparent is None:
        raise ValueError("missing traceparent")
    parsed = validate_traceparent(traceparent)
    if tracestate is not None:
        validate_tracestate(tracestate)
    return parsed.model_copy(update={"tracestate": tracestate, "carrier": carrier})


__all__ = [
    "TraceContextModel", "TraceContextOutput", "validate_traceparent",
    "validate_tracestate", "validate_w3c_carrier",
]
