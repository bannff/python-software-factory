"""Flat ingress and JSON-safe egress DTOs for Auth MCP tools."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, JsonValue

JsonObject = dict[str, JsonValue]


class DTO(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class EmptyInput(DTO):
    pass


class CapabilitiesOutput(DTO):
    module: str
    version: str
    supported_backends: list[str]
    supported_config_schema_versions: list[int]
    authoring_enabled: bool
    running_mode: str
    feature_flags: dict[str, bool]
    tools: dict[str, list[str]]


class HealthOutput(DTO):
    service_name: str
    backend_selected: str
    backend_configured: bool
    connectivity_attempted: bool
    connectivity_ok: bool | None = None
    error: str | None = None


class ConfigSchemaOutput(DTO):
    schema_version: int
    schemas: JsonObject


class VerifyAccessTokenInput(DTO):
    token: str
    required_audience: str | None = None
    required_scopes: list[str] | None = None
    envelope: JsonObject | None = None


class VerifyAccessTokenOutput(DTO):
    ok: bool
    error: str | None = None
    principal: JsonObject | None = None
    claims: JsonObject | None = None
    missing: list[str] | None = None


class TokenInput(DTO):
    token: str
    envelope: JsonObject | None = None


class IntrospectTokenOutput(DTO):
    ok: bool
    active: bool = False
    error: str | None = None
    exp: int | None = None
    sub: str | None = None
    tenant_id: str | None = None


class ResolvePrincipalInput(DTO):
    envelope: JsonObject | None = None


class ResolvePrincipalOutput(DTO):
    ok: bool
    principal: JsonObject | None = None
    source: str
    error: str | None = None


class RefreshTokenInput(DTO):
    refresh_token: str
    scope: str | None = None
    envelope: JsonObject | None = None


class RevokeTokenInput(DTO):
    token: str
    token_type_hint: str | None = None
    envelope: JsonObject | None = None


class TokenOperationOutput(DTO):
    ok: bool
    error: str | None = None
    issued: bool = False
    revoked: bool | None = None
    token_type: str | None = None
    expires_in: int | None = None
    scope: str | None = None
    issued_token_type: str | None = None


class UserInfoInput(DTO):
    access_token: str
    envelope: JsonObject | None = None


class UserInfoOutput(DTO):
    ok: bool
    error: str | None = None
    user_info: JsonObject | None = None


class ExchangeTokenInput(DTO):
    subject_token: str
    subject_token_type: str
    requested_token_type: str | None = None
    audience: str | None = None
    scope: str | None = None
    envelope: JsonObject | None = None


class ValidateBackendConfigInput(DTO):
    dry_run: bool = True


class UpsertBackendConfigInput(DTO):
    name: str
    yaml_or_object: JsonValue
    dry_run: bool = False


class DeleteBackendConfigInput(DTO):
    name: str


class AuthoringStatusOutput(DTO):
    enabled: bool
    config_dir: str
    allowed_paths: list[str]
    schema_versions: list[int]


class AuthoringOperationOutput(DTO):
    ok: bool
    error: str | None = None
    count: int | None = None
    error_count: int = 0
    dry_run: bool | None = None
    deleted: bool | None = None


class ViewsOutput(DTO):
    views: list[JsonObject]
