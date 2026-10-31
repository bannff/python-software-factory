"""Configuration models for telemetry-module.

All configuration is Pydantic-validated for type safety.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


SCHEMA_VERSION = 1


class ServiceSettings(BaseModel):
    """Service identification for telemetry."""
    name: str = Field(min_length=1)
    version: str | None = None


class OTelSettings(BaseModel):
    """OpenTelemetry configuration."""
    enabled: bool = True
    tracing_enabled: bool = True
    metrics_enabled: bool = True
    logging_enabled: bool = True


class AuthoringSettings(BaseModel):
    """Authoring tools configuration."""
    enabled: bool = False


class Settings(BaseModel):
    """Main settings file schema."""
    schema_version: int = Field(default=SCHEMA_VERSION)
    service: ServiceSettings
    otel: OTelSettings = Field(default_factory=OTelSettings)
    authoring: AuthoringSettings = Field(default_factory=AuthoringSettings)


class ExporterConfig(BaseModel):
    """Exporter configuration (OTLP, console, storage, or provenance)."""
    id: str = Field(default="otlp")
    kind: Literal["otlp", "console", "storage", "provenance"] = "otlp"
    endpoint: str = Field(default="")
    protocol: Literal["http/protobuf", "grpc"] = "http/protobuf"
    headers: dict[str, str] = Field(default_factory=dict)
    timeout_seconds: int = Field(default=10, ge=1, le=300)
    # Storage-specific: which store type to persist to
    storage_type: Literal["document", "blob", "graph"] = "document"
    context: dict[str, str] | None = None
    mappings: list[tuple[str, str]] = Field(default_factory=list)
    activation: dict[str, Any] | None = None


class MetricDefinition(BaseModel):
    """Custom metric definition."""
    id: str = Field(min_length=1)
    type: Literal["counter", "histogram"]
    name: str = Field(min_length=1)
    description: str = ""
    unit: str | None = None
    allowed_attributes: list[str] = Field(default_factory=list)


def normalize_otlp_http_endpoint(base: str, signal: Literal["traces", "metrics", "logs"]) -> str:
    """Normalize OTLP HTTP endpoint to include signal path."""
    s = base.rstrip("/")
    if s.endswith(f"/v1/{signal}"):
        return s
    return f"{s}/v1/{signal}"


def filter_attributes(allowed: list[str], attrs: dict[str, Any] | None) -> dict[str, Any]:
    """Filter attributes to only allowed keys."""
    if not attrs:
        return {}
    if not allowed:
        return dict(attrs)
    return {k: v for k, v in attrs.items() if k in set(allowed)}
