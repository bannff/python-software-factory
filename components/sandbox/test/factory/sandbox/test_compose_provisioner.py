"""Tests for ComposeProvisioner — plan and apply for multi-container apps."""
from __future__ import annotations

import pytest

from factory.sandbox.runtime.manifest import (
    ComputeSpec,
    SandboxManifest,
    ServiceDepSpec,
)
from factory.sandbox.runtime.adapters.compose_provisioner import (
    ComposeProvisioner,
)


def _manifest(**overrides) -> SandboxManifest:
    defaults = {
        "app_name": "TestJavaApp",
        "compute": [
            ComputeSpec(type="java_server", name="AppServer",
                        runtime="17", port=8080),
        ],
        "service_deps": [
            ServiceDepSpec(type="rpc", name="RecommendationSvc"),
        ],
    }
    defaults.update(overrides)
    return SandboxManifest(**defaults)


@pytest.mark.asyncio
async def test_plan_creates_container_steps():
    p = ComposeProvisioner()
    plan = await p.plan(_manifest())
    types = {s.action for s in plan.steps}
    assert "create_container" in types
    assert "create_stub" in types
    assert len(plan.steps) == 2


@pytest.mark.asyncio
async def test_plan_skips_lambda_compute():
    m = _manifest(compute=[ComputeSpec(type="lambda", name="fn")])
    p = ComposeProvisioner()
    plan = await p.plan(m)
    container_steps = [s for s in plan.steps if s.action == "create_container"]
    assert len(container_steps) == 0


@pytest.mark.asyncio
async def test_plan_empty_manifest():
    m = SandboxManifest(app_name="Empty")
    p = ComposeProvisioner()
    plan = await p.plan(m)
    assert plan.steps == []


def test_plan_generates_correct_resource_types():
    """Verify plan produces expected resource types for java + rpc."""
    import asyncio
    m = _manifest()
    p = ComposeProvisioner()
    plan = asyncio.run(p.plan(m))
    names = {s.resource_name for s in plan.steps}
    assert "AppServer" in names
    assert "RecommendationSvc" in names


@pytest.mark.asyncio
async def test_plan_java_server_is_create_container():
    m = _manifest()
    p = ComposeProvisioner()
    plan = await p.plan(m)
    java_steps = [s for s in plan.steps if s.resource_name == "AppServer"]
    assert java_steps[0].action == "create_container"
    assert java_steps[0].resource_type == "java_server"


@pytest.mark.asyncio
async def test_plan_rpc_dep_is_create_stub():
    m = _manifest()
    p = ComposeProvisioner()
    plan = await p.plan(m)
    stub_steps = [s for s in plan.steps if s.resource_name == "RecommendationSvc"]
    assert stub_steps[0].action == "create_stub"
    assert stub_steps[0].resource_type == "wiremock"


@pytest.mark.asyncio
async def test_apply_writes_compose_yaml():
    m = _manifest()
    p = ComposeProvisioner()
    plan = await p.plan(m)
    written_cmds: list[str] = []

    async def mock_execute(eid, cmd, timeout=300):
        written_cmds.append(cmd)
        return {"exit_code": 0, "stdout": "", "stderr": ""}

    result = await p.apply("env-1", plan, mock_execute)
    assert result.success is True
    assert result.steps_completed == 2
    assert any("docker-compose.override.yml" in c for c in written_cmds)


@pytest.mark.asyncio
async def test_apply_empty_plan_succeeds():
    m = SandboxManifest(app_name="Empty")
    p = ComposeProvisioner()
    plan = await p.plan(m)
    result = await p.apply("env-1", plan, None)
    assert result.success is True
    assert result.steps_completed == 0
