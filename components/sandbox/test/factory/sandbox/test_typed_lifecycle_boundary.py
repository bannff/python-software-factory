"""Typed MCP-boundary tests for sandbox lifecycle tools."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from factory.mcp_utils.runtime.tool_catalog import ToolCatalog

from factory.mcp_utils.runtime.tool_result import ToolResult
from factory.sandbox.core import EnvironmentStatus
from factory.sandbox.mcp.deterministic import register as register_deterministic
from factory.sandbox.mcp.operational import register
from factory.sandbox.runtime.models import EnvironmentInfo


@pytest.fixture
def runtime() -> MagicMock:
    runtime = MagicMock()
    environment = EnvironmentInfo(
        env_id="env-1", status=EnvironmentStatus.PROVISIONING,
        instance_type="t3.micro", created_at="2026-08-06T00:00:00+00:00",
    )
    runtime.provision = AsyncMock(return_value=environment)
    runtime.terminate = AsyncMock()
    runtime.get_status = AsyncMock(return_value=environment)
    return runtime


async def _tool(runtime: MagicMock, name: str):
    mcp = ToolCatalog("sandbox-boundary-test")
    register(mcp, runtime)
    return await mcp.get_tool(name)


@pytest.mark.asyncio
async def test_provision_has_flat_constrained_schema_and_typed_egress(runtime) -> None:
    tool = await _tool(runtime, "sandbox.provision")
    parameters = tool.fn._mcp_input_model.model_json_schema(mode="validation")["properties"]
    assert parameters["timeout_seconds"]["minimum"] == 60
    assert parameters["timeout_seconds"]["maximum"] == 86400
    result = await tool.fn(instance_type="t3.small", timeout_seconds=120)
    assert isinstance(result, ToolResult)
    assert result.ok is True
    assert result.data.environment.env_id == "env-1"
    runtime.provision.assert_awaited_once()


@pytest.mark.asyncio
async def test_terminate_and_status_use_typed_lifecycle_results(runtime) -> None:
    terminated_tool = await _tool(runtime, "sandbox.terminate")
    status_tool = await _tool(runtime, "sandbox.get_status")
    terminated = await terminated_tool.fn(env_id="env-1")
    found = await status_tool.fn(env_id="env-1")
    assert terminated.data.env_id == "env-1"
    assert found.data.found is True
    assert found.data.environment.env_id == "env-1"
    runtime.terminate.assert_awaited_once_with("env-1")


@pytest.mark.asyncio
async def test_status_not_found_is_typed_data_not_raw_dict(runtime) -> None:
    runtime.get_status = AsyncMock(return_value=None)
    tool = await _tool(runtime, "sandbox.get_status")
    result = await tool.fn(env_id="missing")
    assert isinstance(result, ToolResult)
    assert result.ok is True
    assert result.data.found is False
    assert result.data.error == "Environment not found: missing"


# --- orphan→revoke seam (sandbox side, #768 slice 3) --------------------------


def test_container_reaped_payload_is_strict_and_single_keyed() -> None:
    from pydantic import ValidationError

    from factory.sandbox.runtime.event_payloads import ContainerReapedPayload

    payload = ContainerReapedPayload(
        policy_id="workload:launch-1", env_id="env-1",
        reason="exited", reaped_at="2026-08-06T00:00:00+00:00",
    )
    assert payload.model_dump() == {
        "policy_id": "workload:launch-1", "env_id": "env-1",
        "reason": "exited", "reaped_at": "2026-08-06T00:00:00+00:00",
    }
    # Strict: unknown field (e.g. a stray launch_id) rejected.
    with pytest.raises(ValidationError):
        ContainerReapedPayload(
            policy_id="workload:launch-1", env_id="env-1", reason="exited",
            reaped_at="2026-08-06T00:00:00+00:00", launch_id="launch-1",
        )
    # Strict: reason enum locked to exited/dead.
    with pytest.raises(ValidationError):
        ContainerReapedPayload(
            policy_id="p", env_id="e", reason="killed",
            reaped_at="2026-08-06T00:00:00+00:00",
        )


def test_sweep_emits_reaped_only_for_labeled_workloads(monkeypatch) -> None:
    from factory.sandbox.runtime import reaper
    from factory.sandbox.runtime.runtime import SandboxRuntime

    adapter = MagicMock()
    adapter.sweep_orphans = MagicMock(return_value=[
        {"container_id": "wl-1", "policy_id": "workload:launch-1", "reason": "exited"},
        {"container_id": "plain", "policy_id": None, "reason": "dead"},
    ])
    emitted: list[tuple[str, dict]] = []
    monkeypatch.setattr(reaper, "emit", lambda et, p: emitted.append((et, p)))

    runtime = SandboxRuntime(adapter=adapter, store=MagicMock())
    reaped = runtime.sweep_orphans()

    assert len(reaped) == 2  # count preserved for callers
    assert len(emitted) == 1  # unlabeled orphan emits nothing
    event_type, payload = emitted[0]
    assert event_type == "sandbox.container_reaped"
    assert payload["policy_id"] == "workload:launch-1"
    assert payload["env_id"] == "wl-1"
    assert payload["reason"] == "exited"
    assert set(payload) == {"policy_id", "env_id", "reason", "reaped_at"}


def test_sweep_is_noop_when_adapter_lacks_seam() -> None:
    from factory.sandbox.runtime.runtime import SandboxRuntime

    class _NoSweep:
        pass

    runtime = SandboxRuntime(adapter=_NoSweep(), store=MagicMock())
    assert runtime.sweep_orphans() == []


@pytest.mark.asyncio
async def test_list_live_launch_ids_typed_schema(runtime, monkeypatch) -> None:
    import factory.sandbox.runtime.discovery as discovery

    monkeypatch.setattr(discovery, "discover_live_workloads", lambda: [
        {"policy_id": "workload:launch-1", "env_id": "env-1", "status": "running"},
    ])
    mcp = ToolCatalog("sandbox-det-test")
    register_deterministic(mcp, runtime)
    tool = await mcp.get_tool("sandbox.list_live_launch_ids")
    assert tool.fn._mcp_input_model.model_json_schema()["properties"] == {}
    result = tool.fn()
    assert isinstance(result, ToolResult)
    assert result.ok is True
    assert len(result.data.launches) == 1
    launch = result.data.launches[0]
    assert launch.policy_id == "workload:launch-1"
    assert launch.env_id == "env-1"
    assert launch.status == "running"
