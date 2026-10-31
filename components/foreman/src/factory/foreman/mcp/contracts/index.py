"""Concrete outputs for Foreman's brick-index tools."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class DTO(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class AdapterInfrastructure(DTO):
    services: list[str]


class AdapterInfrastructureMap(DTO):
    keycloak: AdapterInfrastructure | None = None
    authlib_keycloak: AdapterInfrastructure | None = None
    aws: AdapterInfrastructure | None = None
    redis: AdapterInfrastructure | None = None
    chroma: AdapterInfrastructure | None = None
    chroma_server: AdapterInfrastructure | None = None
    neo4j: AdapterInfrastructure | None = None
    bedrock: AdapterInfrastructure | None = None
    s3: AdapterInfrastructure | None = None
    mongodb: AdapterInfrastructure | None = None
    postgres: AdapterInfrastructure | None = None
    aws_document: AdapterInfrastructure | None = None
    aws_sql: AdapterInfrastructure | None = None
    mem0: AdapterInfrastructure | None = None
    agentcore: AdapterInfrastructure | None = None
    cognee: AdapterInfrastructure | None = None
    zep: AdapterInfrastructure | None = None
    seaweedfs: AdapterInfrastructure | None = None


class AdapterGroups(DTO):
    blob: list[str] | None = None
    document: list[str] | None = None
    sql: list[str] | None = None
    graph: list[str] | None = None


class Configuration(DTO):
    env_vars: dict[str, str]


class BrickMetadata(DTO):
    name: str
    type: Literal["component", "base"]
    namespace: str
    description: str | None = None
    mcp_enabled: bool | None = None
    mcp_gateway_host: bool | None = None
    features: list[str] | None = None
    adapters: list[str] | AdapterGroups | None = None
    adapter_infra: AdapterInfrastructureMap | None = None
    mcp_resources: list[str] | None = None
    mcp_prompts: list[str] | None = None
    mcp_tools: list[str] | None = None
    pip_packages: list[str] | None = None
    dependencies: list[str] | None = None
    brick_deps: list[str] | None = None
    domain: str | None = None
    deprecated: bool | None = None
    deprecated_reason: str | None = None
    declared_bricks: list[str] | None = Field(default=None, alias="declared-bricks")
    contract_tools: list[str] | None = None
    meta_tools: list[str] | None = None
    resources: list[str] | None = None
    prompts: list[str] | None = None
    configuration: Configuration | None = None


class BrickGroups(DTO):
    components: list[BrickMetadata]
    bases: list[BrickMetadata]


class InvalidMetadata(DTO):
    path: str
    error: str


class BricksIndexOutput(DTO):
    schema_version: int
    workspace: str
    bricks: BrickGroups
    missing_metadata: list[str]
    invalid_metadata: list[InvalidMetadata]


class WriteBricksIndexOutput(DTO):
    status: str
    path: str
    components_count: int | None = None
    bases_count: int | None = None
    missing_metadata_count: int | None = None
    missing_metadata: list[str] | None = None
    invalid_metadata_count: int | None = None
    invalid_metadata: list[InvalidMetadata] | None = None
    error: str | None = None
