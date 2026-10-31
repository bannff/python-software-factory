"""Strict manifest-provisioning DTOs for the Sandbox MCP surface."""
from __future__ import annotations

from typing import Any

from pydantic import Field

from .contracts import StrictModel


class SandboxComputeSpec(StrictModel):
    type: str
    name: str
    runtime: str = ""
    handler: str = ""
    code_package: str = ""
    port: int = 0


class SandboxDataStoreSpec(StrictModel):
    type: str
    name: str
    config: dict[str, Any] = Field(default_factory=dict)


class SandboxAuthSpec(StrictModel):
    strategy: str = "bypass"
    authorizer_enabled: bool = False
    oauth_provider_enabled: bool = False
    jwt_token: str = ""


class SandboxServiceDepSpec(StrictModel):
    type: str
    name: str
    endpoint: str = ""
    stub_responses: list[dict[str, Any]] = Field(default_factory=list)


class SandboxNetworkSpec(StrictModel):
    ports: list[dict[str, int]] = Field(default_factory=list)
    dns_aliases: list[dict[str, str]] = Field(default_factory=list)


class SandboxManifestDTO(StrictModel):
    app_name: str
    run_id: str = ""
    compute: list[SandboxComputeSpec] = Field(default_factory=list)
    data_stores: list[SandboxDataStoreSpec] = Field(default_factory=list)
    auth: SandboxAuthSpec = Field(default_factory=SandboxAuthSpec)
    service_deps: list[SandboxServiceDepSpec] = Field(default_factory=list)
    network: SandboxNetworkSpec | None = None
    cfn_template: str | None = None
    init_scripts: list[str] = Field(default_factory=list)


class SandboxProvisionStep(StrictModel):
    action: str
    resource_type: str = ""
    resource_name: str = ""
    command: str = ""
    status: str = "pending"


class SandboxProvisionPlan(StrictModel):
    app_name: str
    steps: list[SandboxProvisionStep] = Field(default_factory=list)
    estimated_duration_seconds: int = 0


class SandboxProvisionResult(StrictModel):
    app_name: str
    success: bool
    steps_completed: int = 0
    steps_failed: int = 0
    resources_created: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class ManifestRequest(StrictModel):
    manifest: SandboxManifestDTO


class ManifestValidationResult(StrictModel):
    valid: bool
    errors: list[str] = Field(default_factory=list)
    manifest: SandboxManifestDTO | None = None
    summary: dict[str, int | str | bool] | None = None


class PlanProvisionResult(StrictModel):
    plan: SandboxProvisionPlan


class ApplyProvisionRequest(StrictModel):
    env_id: str = Field(min_length=1, max_length=256)
    plan: SandboxProvisionPlan


class ApplyProvisionResult(StrictModel):
    result: SandboxProvisionResult


__all__ = [
    "ApplyProvisionRequest", "ApplyProvisionResult", "ManifestRequest",
    "ManifestValidationResult", "PlanProvisionResult", "SandboxManifestDTO",
    "SandboxProvisionPlan", "SandboxProvisionResult",
]
