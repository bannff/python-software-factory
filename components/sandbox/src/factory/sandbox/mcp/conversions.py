"""Conversions between strict MCP DTOs and permissive Sandbox runtime models."""
from __future__ import annotations

from typing import Any

from ..runtime.manifest import ProvisionPlan, ProvisionResult, SandboxManifest
from ..runtime.models import EnvironmentInfo, ServiceMockConfig
from .nested_models import SandboxEnvironmentInfo, SandboxServiceMockConfig
from .provision_models import SandboxManifestDTO, SandboxProvisionPlan, SandboxProvisionResult


def to_runtime_environment(value: SandboxEnvironmentInfo) -> EnvironmentInfo:
    return EnvironmentInfo.model_validate(value.model_dump())


def to_mcp_environment(value: EnvironmentInfo) -> SandboxEnvironmentInfo:
    return SandboxEnvironmentInfo.model_validate(value.model_dump())


def to_runtime_service_mocks(value: SandboxServiceMockConfig) -> ServiceMockConfig:
    return ServiceMockConfig.model_validate(value.model_dump())


def to_runtime_manifest(value: SandboxManifestDTO) -> SandboxManifest:
    return SandboxManifest.model_validate(value.model_dump())


def to_mcp_manifest(value: SandboxManifest | dict[str, Any]) -> SandboxManifestDTO:
    return SandboxManifestDTO.model_validate(SandboxManifest.model_validate(value).model_dump())


def to_runtime_plan(value: SandboxProvisionPlan) -> ProvisionPlan:
    return ProvisionPlan.model_validate(value.model_dump())


def to_mcp_plan(value: ProvisionPlan | dict[str, Any]) -> SandboxProvisionPlan:
    return SandboxProvisionPlan.model_validate(ProvisionPlan.model_validate(value).model_dump())


def to_mcp_result(value: ProvisionResult | dict[str, Any]) -> SandboxProvisionResult:
    return SandboxProvisionResult.model_validate(ProvisionResult.model_validate(value).model_dump())
