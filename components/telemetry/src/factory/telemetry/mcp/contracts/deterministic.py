"""DTOs for deterministic Telemetry MCP tools."""
from __future__ import annotations

from .base import DTO, JsonObject


class CapabilitiesOutput(DTO):
    module: str
    version: str
    deterministic_tools: list[str]
    recording_tools: list[str]
    context_tools: list[str]
    admin_tools: list[str]
    capture_tools: list[str] = []
    provenance_tools: list[str] = []
    authoring: JsonObject
    tools: dict[str, list[str]] = {}
    mcp_resources: list[str] = []
    mcp_prompts: list[str] = []


class HealthOutput(DTO):
    ok: bool
    error: str | None = None
    service: JsonObject | None = None
    otel: JsonObject | None = None
    exporters: list[str] = []
    span_exporter: JsonObject | None = None


class RegistryEntry(DTO):
    id: str
    kind: str | None = None
    name: str | None = None
    description: str | None = None
    unit: str | None = None
    enabled: bool | None = None
    attributes: JsonObject | None = None


class MetricRegistryOutput(DTO):
    metrics: list[JsonObject]


class ExporterRegistryOutput(DTO):
    exporters: list[JsonObject]


class MetricsSummaryOutput(DTO):
    started_at: float
    llm: JsonObject
    agent: JsonObject
    tools: JsonObject
    logs: JsonObject
    errors: int


class ConfigSchemaOutput(DTO):
    schema_version: int
    schemas: JsonObject


class ContextOutput(DTO):
    ok: bool
    outcome: str
    carrier: dict[str, str] | None = None
    traceparent: str | None = None
    traceparent_version: str | None = None
    trace_id: str | None = None
    span_id: str | None = None
    trace_flags: int | None = None
    tracestate: str | None = None
    error: str | None = None


class ExtractContextInput(DTO):
    carrier: dict[str, str]


class ViewsOutput(DTO):
    views: list[JsonObject]


class CollectionStatusOutput(DTO):
    """Honest, read-only report of what telemetry collection actually does today."""

    collecting: bool
    sample_rate: float
    redacted_field_names: list[str]
    raw_retention_days: int
    rollup_retention_days: int
    configurable: bool
