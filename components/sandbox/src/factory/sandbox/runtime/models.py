"""Pydantic models for sandbox component."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from ..core import EnvironmentStatus


class SandboxConfig(BaseModel):
    """Sandbox environment configuration."""

    instance_type: str = "t3.micro"
    timeout_seconds: int = Field(default=3600, ge=60, le=86400)
    auto_terminate: bool = True
    ami_id: str | None = None
    security_group_id: str | None = None
    subnet_id: str | None = None
    tags: dict[str, str] = Field(default_factory=dict)


class EnvironmentInfo(BaseModel):
    """Information about a sandbox environment."""

    env_id: str
    status: EnvironmentStatus
    instance_type: str
    created_at: str
    public_ip: str | None = None
    private_ip: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class CommandResult(BaseModel):
    """Result of command execution."""

    success: bool
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int


class FileInfo(BaseModel):
    """Information about a file in the environment."""

    name: str
    path: str
    size_bytes: int
    is_directory: bool
    modified_at: str | None = None


class AuthorizerMockConfig(BaseModel):
    """Authorization service mock configuration."""

    enabled: bool = False
    service_name: str = ""
    operations: list[str] = Field(default_factory=list)
    relationships: list[dict[str, str]] = Field(default_factory=list)
    bypass_mode: str = "authorize_all"  # authorize_all | deny_all | selective


class CredentialStoreMockConfig(BaseModel):
    """Credential store mock configuration."""

    enabled: bool = False
    material_sets: dict[str, dict[str, str]] = Field(default_factory=dict)
    # key = material_set_name, value = {aws_account_id, ...}


class OAuthProviderMockConfig(BaseModel):
    """OAuth 2.0 provider mock configuration."""

    enabled: bool = False
    bypass_mode: str = "disable"  # disable | mock_server
    issuer: str = "https://mock-oauth.localhost"
    token_endpoint: str = "/oauth2/token"


class RpcServiceMockConfig(BaseModel):
    """RPC service mock configuration."""

    enabled: bool = False
    service_stubs: list[dict[str, Any]] = Field(default_factory=list)
    # Each stub: {service_name, endpoint, responses: [{operation, response_body}]}


class CredentialFileMockConfig(BaseModel):
    """Credential file mock configuration."""

    enabled: bool = False
    credential_paths: list[str] = Field(default_factory=list)


class ServiceMockConfig(BaseModel):
    """Aggregate service mock configuration for sandbox environments.

    Populated by recon agents when they discover implicit platform
    service dependencies (authorization, credential store, OAuth
    provider, RPC service, credential file) in a target app's CDK/code.
    Consumed by the sandbox deployer to configure mocks alongside CFN
    infrastructure.
    """

    authorizer: AuthorizerMockConfig = Field(default_factory=AuthorizerMockConfig)
    credential_store: CredentialStoreMockConfig = Field(default_factory=CredentialStoreMockConfig)
    oauth_provider: OAuthProviderMockConfig = Field(default_factory=OAuthProviderMockConfig)
    rpc_service: RpcServiceMockConfig = Field(default_factory=RpcServiceMockConfig)
    credential_file: CredentialFileMockConfig = Field(default_factory=CredentialFileMockConfig)
