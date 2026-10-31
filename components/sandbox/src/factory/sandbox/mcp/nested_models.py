"""Strict nested DTOs used by Sandbox MCP contracts."""
from __future__ import annotations

from typing import Any

from pydantic import Field

from ..core import EnvironmentStatus
from .contracts import StrictModel


class SandboxEnvironmentInfo(StrictModel):
    env_id: str
    status: EnvironmentStatus
    instance_type: str
    created_at: str
    public_ip: str | None = None
    private_ip: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class SandboxAuthorizerMockConfig(StrictModel):
    enabled: bool = False
    service_name: str = ""
    operations: list[str] = Field(default_factory=list)
    relationships: list[dict[str, str]] = Field(default_factory=list)
    bypass_mode: str = "authorize_all"


class SandboxCredentialStoreMockConfig(StrictModel):
    enabled: bool = False
    material_sets: dict[str, dict[str, str]] = Field(default_factory=dict)


class SandboxOAuthProviderMockConfig(StrictModel):
    enabled: bool = False
    bypass_mode: str = "disable"
    issuer: str = "https://mock-oauth.localhost"
    token_endpoint: str = "/oauth2/token"


class SandboxRpcServiceMockConfig(StrictModel):
    enabled: bool = False
    service_stubs: list[dict[str, Any]] = Field(default_factory=list)


class SandboxCredentialFileMockConfig(StrictModel):
    enabled: bool = False
    credential_paths: list[str] = Field(default_factory=list)


class SandboxServiceMockConfig(StrictModel):
    authorizer: SandboxAuthorizerMockConfig = Field(default_factory=SandboxAuthorizerMockConfig)
    credential_store: SandboxCredentialStoreMockConfig = Field(default_factory=SandboxCredentialStoreMockConfig)
    oauth_provider: SandboxOAuthProviderMockConfig = Field(default_factory=SandboxOAuthProviderMockConfig)
    rpc_service: SandboxRpcServiceMockConfig = Field(default_factory=SandboxRpcServiceMockConfig)
    credential_file: SandboxCredentialFileMockConfig = Field(default_factory=SandboxCredentialFileMockConfig)


__all__ = [
    "SandboxAuthorizerMockConfig", "SandboxOAuthProviderMockConfig", "SandboxRpcServiceMockConfig",
    "SandboxEnvironmentInfo", "SandboxCredentialStoreMockConfig", "SandboxServiceMockConfig",
    "SandboxCredentialFileMockConfig",
]
