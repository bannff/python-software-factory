"""SandboxManifest and provisioning plan models.

Declarative specification of what a sandbox environment needs:
compute, data stores, auth, service deps, network. The manifest
is translated into a ProvisionPlan by a ProvisionerPort adapter.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ComputeSpec(BaseModel):
    """Compute resource specification."""

    type: str  # "lambda" | "java_server" | "ecs" | "container"
    name: str
    runtime: str = ""  # "python3.12" | "java8" | "java17"
    handler: str = ""
    code_package: str = ""  # build-system package name
    port: int = 0


class DataStoreSpec(BaseModel):
    """Data store resource specification."""

    type: str  # "dynamodb" | "s3" | "sqs" | "sns" | "rds" | "elasticache"
    name: str
    config: dict[str, Any] = Field(default_factory=dict)
    # For DynamoDB: {key_schema: [...], gsi: [...], attributes: [...]}
    # For S3: {} (just bucket name)
    # For SQS: {dlq: bool}


class AuthSpec(BaseModel):
    """Authentication/authorization specification."""

    strategy: str = "bypass"  # "bypass" | "mock_server" | "real"
    authorizer_enabled: bool = False
    oauth_provider_enabled: bool = False
    jwt_token: str = ""  # Pre-built JWT for testing


class ServiceDepSpec(BaseModel):
    """External service dependency specification."""

    type: str  # "rpc" | "rest" | "graphql"
    name: str
    endpoint: str = ""
    stub_responses: list[dict[str, Any]] = Field(default_factory=list)


class NetworkSpec(BaseModel):
    """Network configuration specification."""

    ports: list[dict[str, int]] = Field(default_factory=list)
    dns_aliases: list[dict[str, str]] = Field(default_factory=list)


class SandboxManifest(BaseModel):
    """Declarative manifest describing a full sandbox environment."""

    app_name: str
    run_id: str = ""
    compute: list[ComputeSpec] = Field(default_factory=list)
    data_stores: list[DataStoreSpec] = Field(default_factory=list)
    auth: AuthSpec = Field(default_factory=AuthSpec)
    service_deps: list[ServiceDepSpec] = Field(default_factory=list)
    network: NetworkSpec | None = None
    cfn_template: str | None = None  # Pre-built CFN if available
    init_scripts: list[str] = Field(default_factory=list)


class ProvisionStep(BaseModel):
    """Single step in a provision plan."""

    action: str  # "create_table" | "create_bucket" | "deploy_cfn" | ...
    resource_type: str = ""
    resource_name: str = ""
    command: str = ""  # CLI command or CFN template
    status: str = "pending"


class ProvisionPlan(BaseModel):
    """Ordered list of steps to provision a sandbox environment."""

    app_name: str
    steps: list[ProvisionStep] = Field(default_factory=list)
    estimated_duration_seconds: int = 0


class ProvisionResult(BaseModel):
    """Outcome of applying a provision plan."""

    app_name: str
    success: bool
    steps_completed: int = 0
    steps_failed: int = 0
    resources_created: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
