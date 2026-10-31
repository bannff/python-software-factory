"""Pydantic v2 MCP boundary models for sandbox lifecycle tools."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from .contracts import StrictModel
from .nested_models import SandboxEnvironmentInfo
from ..runtime.peer_network import PeerNetworkSpec


class SandboxProvisionRequest(StrictModel):
    instance_type: str = Field(default="t3.micro", min_length=1, max_length=128)
    timeout_seconds: int = Field(default=3600, ge=60, le=86400)
    auto_terminate: bool = True
    ami_id: str | None = Field(default=None, min_length=1, max_length=256)
    profile: str | None = Field(default=None, min_length=1, max_length=128)
    device_preset: str | None = Field(
        default=None, pattern=r"^[a-z0-9][a-z0-9_-]{0,127}$",
    )
    peer_network: PeerNetworkSpec | None = None

    @model_validator(mode="after")
    def peer_network_requires_profile(self) -> "SandboxProvisionRequest":
        if self.peer_network is not None and self.profile is None:
            raise ValueError("peer_network requires a sandbox profile")
        return self


class SandboxProvisionResult(StrictModel):
    success: Literal[True] = True
    environment: SandboxEnvironmentInfo
    profile: str | None = None
    device_preset: str | None = None


class SandboxEnvironmentRequest(StrictModel):
    env_id: str = Field(min_length=1, max_length=256)


class SandboxTerminateResult(StrictModel):
    success: Literal[True] = True
    env_id: str


class SandboxStatusResult(StrictModel):
    found: bool
    environment: SandboxEnvironmentInfo | None = None
    error: str | None = None


__all__ = [
    "SandboxEnvironmentRequest",
    "SandboxProvisionRequest",
    "SandboxProvisionResult",
    "SandboxStatusResult",
    "SandboxTerminateResult",
]
