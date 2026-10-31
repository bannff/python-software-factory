"""Typed lifecycle MCP tools for the sandbox component."""

from __future__ import annotations

from typing import TYPE_CHECKING

from typing import Any
from pydantic import Field

from factory.mcp_utils.interface import ok, operational
from factory.mcp_utils.runtime.tool_result import ToolResult

from ..runtime.models import SandboxConfig
from ..runtime.peer_network import PeerNetworkSpec
from .conversions import to_mcp_environment
from .models import (
    SandboxEnvironmentRequest, SandboxProvisionRequest, SandboxProvisionResult,
    SandboxStatusResult, SandboxTerminateResult,
)

if TYPE_CHECKING:
    from ..runtime.runtime import SandboxRuntime


def register(mcp: Any, runtime: "SandboxRuntime") -> None:
    """Register typed sandbox lifecycle operations."""

    @mcp.tool(name="sandbox.provision")
    @operational(input_model=SandboxProvisionRequest, output_model=SandboxProvisionResult)
    async def provision(
        instance_type: str = Field(default="t3.micro", min_length=1, max_length=128),
        timeout_seconds: int = Field(default=3600, ge=60, le=86400),
        auto_terminate: bool = True,
        ami_id: str | None = Field(default=None, min_length=1, max_length=256),
        profile: str | None = Field(default=None, min_length=1, max_length=128),
        device_preset: str | None = Field(
            default=None, pattern=r"^[a-z0-9][a-z0-9_-]{0,127}$",
        ),
        peer_network: PeerNetworkSpec | None = None,
    ) -> ToolResult[SandboxProvisionResult]:
        """Provision a sandbox environment."""
        environment = await runtime.provision(
            SandboxConfig(
                instance_type=instance_type, timeout_seconds=timeout_seconds,
                auto_terminate=auto_terminate, ami_id=ami_id,
            ),
            profile=profile,
            device_preset=device_preset,
            peer_network=peer_network,
        )
        return ok(SandboxProvisionResult(
            environment=to_mcp_environment(environment), profile=profile,
            device_preset=device_preset,
        ))

    @mcp.tool(name="sandbox.terminate")
    @operational(input_model=SandboxEnvironmentRequest, output_model=SandboxTerminateResult)
    async def terminate(
        env_id: str = Field(min_length=1, max_length=256),
    ) -> ToolResult[SandboxTerminateResult]:
        """Terminate a sandbox environment."""
        await runtime.terminate(env_id)
        return ok(SandboxTerminateResult(env_id=env_id))

    @mcp.tool(name="sandbox.get_status")
    @operational(input_model=SandboxEnvironmentRequest, output_model=SandboxStatusResult)
    async def get_status(
        env_id: str = Field(min_length=1, max_length=256),
    ) -> ToolResult[SandboxStatusResult]:
        """Get sandbox environment status."""
        environment = await runtime.get_status(env_id)
        if environment is None:
            return ok(SandboxStatusResult(found=False, error=f"Environment not found: {env_id}"))
        return ok(SandboxStatusResult(
            found=True, environment=to_mcp_environment(environment),
        ))
