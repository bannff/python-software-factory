"""Tests for CfnProvisioner — plan and apply from SandboxManifest."""
from __future__ import annotations

import json
import pytest

from factory.sandbox.runtime.manifest import (
    ComputeSpec,
    DataStoreSpec,
    ProvisionPlan,
    SandboxManifest,
)
from factory.sandbox.runtime.adapters.cfn_provisioner import CfnProvisioner


def _manifest(**overrides) -> SandboxManifest:
    """Build a minimal test manifest."""
    defaults = {
        "app_name": "TestApp",
        "data_stores": [
            DataStoreSpec(type="dynamodb", name="users-table"),
            DataStoreSpec(type="s3", name="assets-bucket"),
            DataStoreSpec(type="sqs", name="work-queue"),
        ],
    }
    defaults.update(overrides)
    return SandboxManifest(**defaults)


@pytest.mark.asyncio
async def test_plan_creates_steps_for_data_stores():
    p = CfnProvisioner()
    plan = await p.plan(_manifest())
    assert plan.app_name == "TestApp"
    assert len(plan.steps) == 3
    types = {s.resource_type for s in plan.steps}
    assert types == {"DynamoDB", "S3", "SQS"}
    assert all(s.action == "create_resource" for s in plan.steps)


@pytest.mark.asyncio
async def test_plan_includes_lambda_compute():
    m = _manifest(compute=[ComputeSpec(type="lambda", name="handler")])
    p = CfnProvisioner()
    plan = await p.plan(m)
    compute_steps = [s for s in plan.steps if s.resource_type == "Lambda"]
    assert len(compute_steps) == 1
    assert compute_steps[0].resource_name == "handler"


@pytest.mark.asyncio
async def test_plan_includes_cfn_template():
    m = _manifest(cfn_template='{"Resources": {}}')
    p = CfnProvisioner()
    plan = await p.plan(m)
    cfn_steps = [s for s in plan.steps if s.action == "deploy_cfn"]
    assert len(cfn_steps) == 1
    assert cfn_steps[0].resource_name == "TestApp-custom"


@pytest.mark.asyncio
async def test_plan_includes_init_scripts():
    m = _manifest(init_scripts=["bash /tmp/init.sh"])
    p = CfnProvisioner()
    plan = await p.plan(m)
    script_steps = [s for s in plan.steps if s.action == "run_script"]
    assert len(script_steps) == 1
    assert script_steps[0].command == "bash /tmp/init.sh"


@pytest.mark.asyncio
async def test_plan_empty_manifest():
    m = SandboxManifest(app_name="Empty")
    p = CfnProvisioner()
    plan = await p.plan(m)
    assert plan.steps == []
    assert plan.estimated_duration_seconds == 0


@pytest.mark.asyncio
async def test_apply_deploys_cfn_and_reports_success():
    m = _manifest()
    p = CfnProvisioner()
    plan = await p.plan(m)

    async def mock_execute(eid, cmd, timeout=300):
        return {"exit_code": 0, "stdout": "{}", "stderr": ""}

    result = await p.apply("env-1", plan, mock_execute)
    assert result.success is True
    assert result.steps_completed == 3
    assert result.steps_failed == 0
    assert len(result.resources_created) == 3


@pytest.mark.asyncio
async def test_apply_reports_cfn_failure():
    m = _manifest()
    p = CfnProvisioner()
    plan = await p.plan(m)

    async def mock_execute(eid, cmd, timeout=300):
        return {"exit_code": 1, "stdout": "error", "stderr": "deploy failed"}

    result = await p.apply("env-1", plan, mock_execute)
    assert result.success is False
    assert result.steps_failed > 0
    assert len(result.errors) > 0


@pytest.mark.asyncio
async def test_apply_runs_init_scripts():
    m = _manifest(init_scripts=["echo hello"])
    p = CfnProvisioner()
    plan = await p.plan(m)

    calls: list[str] = []

    async def mock_execute(eid, cmd, timeout=300):
        calls.append(cmd)
        return {"exit_code": 0, "stdout": "ok", "stderr": ""}

    result = await p.apply("env-1", plan, mock_execute)
    assert result.success is True
    # Should have CFN deploy + init script
    assert any("echo hello" in c for c in calls)
