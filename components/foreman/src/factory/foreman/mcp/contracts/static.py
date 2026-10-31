"""Concrete outputs for Foreman's static contract and guardrail tools."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class DTO(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class ToolingOutput(DTO):
    deterministic: list[str]
    operational: list[str]
    authoring: list[str]


class CapabilitiesOutput(DTO):
    schema_version: int
    features: list[str]
    tooling: ToolingOutput
    resources: list[str]
    prompts: list[str]


class HealthDetails(DTO):
    server: str
    poly_check: str


class HealthOutput(DTO):
    status: str
    details: HealthDetails


class EmptySchemaProperties(DTO):
    pass


class ConfigSchema(DTO):
    type: str
    additionalProperties: bool
    properties: EmptySchemaProperties


class ConfigSchemaOutput(DTO):
    schema_version: int
    config_schema: ConfigSchema


class ControlPlane(DTO):
    system: str
    work: str
    changes: str
    decisions: str
    knowledge: str


class ExecutionPlane(DTO):
    foreman: str


class GuardrailLinks(DTO):
    issues: str
    pulls: str
    discussions: str
    wiki: str
    readme: str
    walkthrough: str


class GuardrailsOutput(DTO):
    schema_version: int
    control_plane: ControlPlane
    execution_plane: ExecutionPlane
    workflow_example: list[str]
    links: GuardrailLinks


class WorkspaceInfoOutput(DTO):
    success: bool
    workspace: str
    components_count: int
    bases_count: int
    projects_count: int
    components: list[str]
    bases: list[str]
    projects: dict[str, list[str]]
