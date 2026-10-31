"""Regression tests for recursive same-brick Sandbox MCP DTOs."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from factory.mcp_utils.runtime.tool_catalog import ToolCatalog
from pydantic import ValidationError

from factory.sandbox.mcp.extended_models import SandboxReconResource, SandboxServiceMocksRequest
from factory.sandbox.mcp.models import SandboxProvisionResult, SandboxStatusResult
from factory.sandbox.mcp.provision_models import (
    ApplyProvisionRequest, ApplyProvisionResult, ManifestRequest,
    ManifestValidationResult, PlanProvisionResult,
)
from factory.sandbox.mcp.provision_tools import register as register_provision_tools
from factory.sandbox.runtime.manifest import ProvisionPlan, ProvisionResult, SandboxManifest
from factory.sandbox.runtime.models import EnvironmentInfo


def test_recon_resource_rejects_nested_unexpected_fields() -> None:
    with pytest.raises(ValidationError, match="unexpected"):
        SandboxReconResource.model_validate({"type": "S3", "name": "bucket", "unexpected": True})


def test_service_mocks_reject_nested_unexpected_fields() -> None:
    with pytest.raises(ValidationError, match="unexpected"):
        SandboxServiceMocksRequest.model_validate({
            "env_id": "env-1", "config": {"authorizer": {"enabled": True, "unexpected": True}},
        })


@pytest.mark.parametrize("contract,payload", [
    (ManifestRequest, {"manifest": {"app_name": "app", "compute": [{"type": "lambda", "name": "fn", "unexpected": 1}]}}),
    (ApplyProvisionRequest, {"env_id": "env-1", "plan": {"app_name": "app", "steps": [{"action": "deploy", "unexpected": 1}]}}),
])
def test_manifest_and_plan_requests_reject_nested_unexpected_fields(contract, payload) -> None:
    with pytest.raises(ValidationError, match="unexpected"):
        contract.model_validate(payload)


def test_manifest_plan_and_result_outputs_are_same_brick_dtos() -> None:
    manifest = SandboxManifest(app_name="app", data_stores=[{"type": "s3", "name": "bucket"}])
    plan = ProvisionPlan(app_name="app")
    result = ProvisionResult(app_name="app", success=True)
    environment = EnvironmentInfo(
        env_id="env-1", status="running", instance_type="mock", created_at="now",
    )
    validation = ManifestValidationResult(valid=True, manifest=manifest.model_dump())
    planned = PlanProvisionResult(plan=plan.model_dump())
    applied = ApplyProvisionResult(result=result.model_dump())
    provisioned = SandboxProvisionResult(environment=environment.model_dump())
    status = SandboxStatusResult(found=True, environment=environment.model_dump())
    for value in (validation.manifest, planned.plan, applied.result, provisioned.environment, status.environment):
        assert value.__class__.__module__.startswith("factory.sandbox.mcp")


@pytest.mark.asyncio
async def test_provision_wrappers_convert_strict_dtos_at_the_runtime_boundary() -> None:
    runtime = MagicMock()
    runtime.execute = AsyncMock()
    mcp = ToolCatalog("sandbox-strict-provision-test")
    register_provision_tools(mcp, runtime)
    manifest = {"app_name": "app", "data_stores": [{"type": "s3", "name": "bucket"}]}
    validated = await (await mcp.get_tool("sandbox.validate_manifest")).fn(manifest=manifest)
    planned = await (await mcp.get_tool("sandbox.plan_provision")).fn(manifest=manifest)
    applied = await (await mcp.get_tool("sandbox.apply_provision")).fn(
        env_id="env-1", plan={"app_name": "app"},
    )
    assert validated.data.manifest.__class__.__module__.startswith("factory.sandbox.mcp")
    assert planned.data.plan.__class__.__module__.startswith("factory.sandbox.mcp")
    assert applied.data.result.__class__.__module__.startswith("factory.sandbox.mcp")
