"""Strict Pydantic v2 DTOs for Config's public MCP boundary."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, JsonValue


class ConfigDTO(BaseModel):
    """Reject unknown or coerced values at the Config MCP boundary."""

    model_config = ConfigDict(extra="forbid", strict=True)


class EmptyInput(ConfigDTO):
    """Input DTO for argument-free Config tools."""


class CapabilitiesOutput(ConfigDTO):
    name: str
    version: str
    backends: list[str]
    features: list[str]
    mcp_resources: list[str]
    mcp_prompts: list[str]


class ConfigHealthOutput(ConfigDTO):
    healthy: bool
    backend: str


class HealthCheckOutput(ConfigDTO):
    healthy: bool
    environment: str
    configs: dict[str, ConfigHealthOutput]
    message: str | None = None


class SchemaPropertyOutput(ConfigDTO):
    type: str
    enum: list[str] | None = None
    description: str


class ConfigSchemaOutput(ConfigDTO):
    type: str
    properties: dict[str, SchemaPropertyOutput]
    required: list[str]


class EnvironmentOutput(ConfigDTO):
    environment: str


class AwsIdentityInput(ConfigDTO):
    force_refresh: bool = False


class AwsIdentityOutput(ConfigDTO):
    available: bool
    profile: str | None = None
    region: str | None = None
    account_id: str | None = None
    identity_arn: str | None = None
    user_id: str | None = None
    error: str | None = None


class GetInput(ConfigDTO):
    key: str
    default: str | None = None


class GetOutput(ConfigDTO):
    key: str
    value: JsonValue | None = None
    found: bool


class SetInput(ConfigDTO):
    key: str
    value: str


class SetOutput(ConfigDTO):
    key: str
    success: bool


class DeleteInput(ConfigDTO):
    key: str


class DeleteOutput(ConfigDTO):
    key: str
    deleted: bool


class PrefixInput(ConfigDTO):
    prefix: str = ""


class KeysOutput(ConfigDTO):
    prefix: str
    keys: list[str]
    count: int


class GetAllOutput(ConfigDTO):
    prefix: str
    values: dict[str, JsonValue]
    count: int


class GetTypedInput(ConfigDTO):
    key: str
    value_type: str = "str"
    default: str | None = None


class GetTypedOutput(ConfigDTO):
    key: str
    value: str | int | bool | float | None = None
    type: str
    found: bool


__all__ = [
    "AwsIdentityInput", "AwsIdentityOutput", "CapabilitiesOutput", "ConfigDTO",
    "ConfigHealthOutput", "ConfigSchemaOutput", "DeleteInput", "DeleteOutput",
    "EmptyInput", "EnvironmentOutput", "GetAllOutput", "GetInput", "GetOutput",
    "GetTypedInput", "GetTypedOutput", "HealthCheckOutput", "KeysOutput",
    "PrefixInput", "SchemaPropertyOutput", "SetInput", "SetOutput",
]
