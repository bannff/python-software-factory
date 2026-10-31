"""Typed output schemas for deterministic Sandbox MCP tools."""
from __future__ import annotations
from typing import Any, Literal
from pydantic import Field
from .contracts import StrictModel

class CapabilitiesResult(StrictModel):
    name: str
    version: str
    tools: dict[str, list[str]]
    adapters: list[str]
    features: list[str]
class HealthResult(StrictModel):
    healthy: bool
    adapter: dict[str, Any]
    store: dict[str, Any]
    active_environments: int = Field(ge=0)
    discovered_environments: int = Field(ge=0)
    advisory: str | None = None
class ConfigSchemaResult(StrictModel):
    type: str
    properties: dict[str, dict[str, Any]]
class ProfileInfo(StrictModel):
    image: str
    ports: dict[str, str]  # host:container, mirrors SandboxProfile.ports
    health_check_url: str | None = None
    platform: str | None = None
    cpus: float | None = None
    memory_mb: int | None = None
    device_target: dict[str, str | None] | None = None
class ProfilesResult(StrictModel):
    profiles: dict[str, ProfileInfo]
class ProxyEnvelopeInfo(StrictModel):
    platform: Literal["linux/arm64", "linux/amd64"]
    cpus: float = Field(gt=0, allow_inf_nan=False)
    memory_mb: int = Field(ge=64)
class DevicePresetInfo(StrictModel):
    name: str
    vendor: str
    model: str
    variant: str | None = None
    form_factor: Literal["phone", "tablet", "rugged_handheld", "single_board"]
    os_family: Literal["ios", "ipados", "android", "linux"]
    fidelity: Literal["linux_proxy"]
    source_url: str
    proxy: ProxyEnvelopeInfo
class DevicePresetsResult(StrictModel):
    presets: dict[str, DevicePresetInfo]
class LiveLaunchInfo(StrictModel):
    policy_id: str
    env_id: str
    status: str
class LiveLaunchesResult(StrictModel):
    launches: list[LiveLaunchInfo]
