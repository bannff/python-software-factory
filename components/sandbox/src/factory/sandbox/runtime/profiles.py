"""Sandbox workload profiles for Docker container configuration.

Legacy profile-only provisioning uses one container; selecting a device preset
creates a separate named container for each target.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .adapters.secret_mounts import SecretRef
from .peer_network import PeerNetworkSpec


class DeviceTarget(BaseModel):
    """Device being approximated; Docker execution remains Linux."""

    model_config = ConfigDict(extra="forbid")

    family: Literal["iphone", "ipad", "android_phone", "android_tablet", "other"]
    model: str | None = None
    os_version: str | None = None
    fidelity: Literal["linux_proxy"] = "linux_proxy"


class SandboxProfile(BaseModel):
    """Configuration for a single-container sandbox target."""

    # Fail loud on typo'd keys in hand-authored profile YAML — a silently
    # ignored key would yield a container that is up but missing tooling.
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)

    name: str
    image: str
    ports: dict[str, str] = Field(default_factory=dict)  # host:container
    entrypoint: list[str] | None = None  # None = use image default
    health_check_url: str | None = None
    health_check_timeout: int = 60
    container_name: str = "factory-sandbox"
    replace_existing: bool = True
    shell: str = "/bin/sh"
    env_vars: dict[str, str] = Field(default_factory=dict)
    # Docker launch envelope. Limits bound the container; they do not emulate
    # a phone's SoC, operating system, radios, or power behavior.
    platform: Literal["linux/amd64", "linux/arm64"] | None = None
    cpus: float | None = Field(default=None, gt=0)
    memory_mb: int | None = Field(default=None, gt=0)
    device_target: DeviceTarget | None = None
    # Commands run once, in order, right after provision (e.g. install tooling).
    # Best-effort: a non-zero exit is logged, not fatal. Never put secrets here.
    setup_commands: list[str] = Field(default_factory=list)
    # Host-trusted symbolic names only. Source paths are configured by the
    # Sandbox server process and resolved transiently before Docker launch.
    secret_refs: list[SecretRef] = Field(default_factory=list)
    # Optional shared, Sandbox-owned Docker bridge for separate peer devices.
    peer_network: PeerNetworkSpec | None = None

    @field_validator("secret_refs")
    @classmethod
    def unique_secret_refs(cls, refs: list[SecretRef]) -> list[SecretRef]:
        if len(refs) != len(set(refs)):
            raise ValueError("secret_refs must not contain duplicates")
        return refs


BUILTIN_PROFILES: dict[str, SandboxProfile] = {
    "idor_warehouse": SandboxProfile(
        name="idor_warehouse",
        image="python:3.11-slim",
        ports={"5050": "5000"},
        shell="/bin/bash",
        health_check_url="http://localhost:5050/health",
        entrypoint=["sleep", "infinity"],  # user uploads app + installs deps via execute
    ),
    "webgoat": SandboxProfile(
        name="webgoat",
        image="webgoat/webgoat:latest",
        ports={"8080": "8080", "9090": "9090"},
        health_check_url="http://localhost:8080/WebGoat",
        health_check_timeout=90,
    ),
    "dvwa": SandboxProfile(
        name="dvwa",
        image="vulnerables/web-dvwa:latest",
        ports={"8080": "80"},
        health_check_url="http://localhost:8080/login.php",
    ),
    "vampi": SandboxProfile(
        name="vampi",
        image="erev0s/vampi:latest",
        ports={"5050": "5000"},
        health_check_url="http://localhost:5050/",
    ),
    "juice_shop": SandboxProfile(
        name="juice_shop",
        image="bkimminich/juice-shop:latest",
        ports={"3000": "3000"},
        health_check_url="http://localhost:3000",
    ),
}


def resolve_profile(name_or_config: str | dict) -> SandboxProfile:
    """Resolve a profile name or raw config dict to SandboxProfile.

    Resolution precedence for a name (built-ins/defaults win over user overlay,
    mirroring the persona registry's built-ins-win rule):
      1. code ``BUILTIN_PROFILES``
      2. packaged default YAML (shipped with the brick)
      3. user ``<name>.yaml`` under ``SANDBOX_PROFILES_DIR``
    """
    if isinstance(name_or_config, str):
        if name_or_config in BUILTIN_PROFILES:
            return BUILTIN_PROFILES[name_or_config]
        from .profile_defaults import load_default_profile
        from .profile_store import load_yaml_profile

        default_profile = load_default_profile(name_or_config)
        if default_profile is not None:
            return default_profile
        yaml_profile = load_yaml_profile(name_or_config)
        if yaml_profile is not None:
            return yaml_profile
        available = list_profiles()
        raise ValueError(f"Unknown profile: {name_or_config}. Available: {available}")
    return SandboxProfile(**name_or_config)


def list_profiles() -> list[str]:
    """Return available profile names (built-ins ∪ packaged defaults ∪ user YAML).

    Deduplicated with built-ins-first ordering; a user YAML that collides with a
    built-in or packaged default is elided (the built-in/default wins).
    """
    from .profile_defaults import list_default_profile_names
    from .profile_store import list_yaml_profile_names

    names = list(BUILTIN_PROFILES.keys())
    for name in list_default_profile_names() + list_yaml_profile_names():
        if name not in names:
            names.append(name)
    return names
