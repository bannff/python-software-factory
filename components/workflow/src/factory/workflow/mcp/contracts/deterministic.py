"""DTOs for deterministic Workflow MCP tools."""
from __future__ import annotations

from .base import DTO, JsonObject


class CapabilitiesOutput(DTO):
    schema_versions: JsonObject
    supported_storage_backends: list[str]
    supported_executor_backends: list[str]
    current_executor: str
    authoring_enabled: bool
    running_mode: str
    feature_flags: JsonObject


class HealthOutput(DTO):
    status: str
    storage: JsonObject
    executor: JsonObject
    durable_named_mcp_ready: bool
    last_error: str | None = None


class ConfigSchemaOutput(DTO):
    settings_schema: JsonObject
    workflow_definition_schema: JsonObject


class WorkflowSummary(DTO):
    id: str
    name: str
    version: int
    tags: list[str]
    schema_version: str


class WorkflowRegistryOutput(DTO):
    workflows: list[WorkflowSummary]


class ExecutorStatusOutput(DTO):
    ok: bool
    backend: str
    details: JsonObject
