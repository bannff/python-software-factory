"""Strict Pydantic v2 DTOs for Logger's public MCP boundary."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator

from factory.mcp_utils.interface import is_bounded_json

_MAX_TEXT = 65_536
_MAX_RECORDS = 1_000


class StrictModel(BaseModel):
    """Reject unknown kwargs and coercion at Logger's public boundary."""

    model_config = ConfigDict(extra="forbid", strict=True)


class EmptyInput(StrictModel):
    """Input DTO for no-argument contract and admin tools."""


class CapabilitiesOutput(StrictModel):
    """Machine-readable Logger capability document."""

    document: dict[str, JsonValue]


LogLevelValue = Literal["debug", "info", "warning", "error", "critical"]
JsonObject = dict[str, JsonValue]


class SafeSinkHealthOutput(StrictModel):
    """Sink health projection without filesystem details."""

    backend: str
    writable: bool
    log_size: int | None = Field(default=None, ge=0)
    exists: bool | None = None


class HealthOutput(StrictModel):
    """Logger health with a filesystem-safe sink projection."""

    status: Literal["healthy", "degraded"]
    sink: SafeSinkHealthOutput


class ConfigSchemaOutput(StrictModel):
    """Logger configuration schema document."""

    document: dict[str, JsonValue]


class LogInput(StrictModel):
    """Flat bounded payload shared by all level-specific log writers."""

    message: str = Field(min_length=1, max_length=_MAX_TEXT)
    source: str | None = Field(default=None, max_length=256)
    run_id: str | None = Field(default=None, max_length=256)
    context: dict[str, JsonValue] | None = None

    @field_validator("context")
    @classmethod
    def _bounded_context(
        cls, value: dict[str, JsonValue] | None,
    ) -> dict[str, JsonValue] | None:
        if value is not None and not is_bounded_json(value):
            raise ValueError("context must be bounded JSON")
        return value


class LogOutput(StrictModel):
    """Safe result of writing one logger record."""

    status: Literal["logged"]
    level: Literal["debug", "info", "warning", "error", "critical"]
    timestamp: str


class TailInput(StrictModel):
    """Flat bounded tail query."""

    lines: int = Field(default=20, ge=1, le=_MAX_RECORDS)


class SearchInput(StrictModel):
    """Flat bounded log search query."""

    level: Literal["debug", "info", "warning", "error", "critical"] | None = None
    source: str | None = Field(default=None, max_length=256)
    run_id: str | None = Field(default=None, max_length=256)
    limit: int = Field(default=100, ge=1, le=_MAX_RECORDS)


class LogRecordOutput(StrictModel):
    """Only record fields emitted by LoggerRuntime's query projection."""

    timestamp: str
    level: Literal["debug", "info", "warning", "error", "critical"]
    message: str
    source: str | None = None
    run_id: str | None = None
    context: dict[str, JsonValue] = Field(default_factory=dict)

    @field_validator("context")
    @classmethod
    def _bounded_context(cls, value: dict[str, JsonValue]) -> dict[str, JsonValue]:
        if not is_bounded_json(value):
            raise ValueError("context must be bounded JSON")
        return value


class RecordsOutput(StrictModel):
    """Bounded query response with an explicit result count."""

    records: list[LogRecordOutput] = Field(max_length=_MAX_RECORDS)
    count: int = Field(ge=0, le=_MAX_RECORDS)


class ClearOutput(StrictModel):
    """Safe clear outcome; intentionally excludes the log filesystem path."""

    status: Literal["cleared"]
