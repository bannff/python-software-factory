"""Typed lifecycle MCP tools for the sandbox component."""

from __future__ import annotations

from typing import TYPE_CHECKING

from typing import Any
from pydantic import Field

from factory.mcp_utils.interface import TypedToolFailure, ok, operational
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


def _check_names(profile: str | None, device_preset: str | None) -> None:
    """Unknown names are the common user error; give them their own codes."""
    if profile:
        from ..runtime.profiles import resolve_profile
        try:
            resolve_profile(profile)
        except Exception as exc:  # noqa: BLE001 - any resolution failure means unusable
            raise TypedToolFailure("unknown_profile", profile) from exc
    if device_preset:
        from ..runtime.device_presets import resolve_device_preset
        try:
            resolve_device_preset(device_preset)
        except Exception as exc:  # noqa: BLE001
            raise TypedToolFailure("unknown_device_preset", device_preset) from exc


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
        _check_names(profile, device_preset)
        try:
            environment = await runtime.provision(
                SandboxConfig(
                    instance_type=instance_type, timeout_seconds=timeout_seconds,
                    auto_terminate=auto_terminate, ami_id=ami_id,
                ),
                profile=profile,
                device_preset=device_preset,
                peer_network=peer_network,
            )
        except ValueError as exc:
            raise TypedToolFailure("provision_invalid", str(exc)) from exc
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
        if await runtime.get_status(env_id) is None:
            raise TypedToolFailure("env_not_found", env_id)
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
