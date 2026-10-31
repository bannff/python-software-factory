"""Strict DTOs for API base public MCP tools."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue


class StrictModel(BaseModel):
    """Reject unknown and coerced values at the MCP boundary."""

    model_config = ConfigDict(extra="forbid", strict=True)


class EmptyInput(StrictModel):
    """Input DTO for a tool with no public arguments."""


class CapabilitiesOutput(StrictModel):
    name: str
    version: str
    type: Literal["base"]
    backends: list[str]
    features: list[str]


class HealthOutput(StrictModel):
    healthy: bool
    adapter: str
    routes_count: int = Field(ge=0)
    error: str | None = None


class ConfigPropertyOutput(StrictModel):
    type: str
    enum: list[str] | None = None
    description: str | None = None
    default: str | None = None


class ConfigSchemaOutput(StrictModel):
    type: Literal["object"]
    properties: dict[str, ConfigPropertyOutput]


class RouteOutput(StrictModel):
    path: str
    method: str
    handler: str
    tags: list[str]


class RoutesOutput(StrictModel):
    routes: list[RouteOutput]
    count: int = Field(ge=0)


class OpenAPISchemaOutput(StrictModel):
    status: Literal["supported", "unsupported"]
    supported: bool
    document: JsonValue | None = None
    error: str | None = None


class AddRouteInput(StrictModel):
    path: str
    method: str = "GET"
    handler_name: str = "noop"
    tags: list[str] | None = None


class AddRouteOutput(StrictModel):
    registered: bool
    path: str
    method: str
    handler: str


class RemoveRouteInput(StrictModel):
    path: str
    method: str = "GET"


class RemoveRouteOutput(StrictModel):
    removed: bool
    path: str
    method: str
    reason: str | None = None
    routes_count: int | None = Field(default=None, ge=0)


class SwitchAdapterInput(StrictModel):
    adapter_type: str


class SwitchAdapterOutput(StrictModel):
    switched: bool
    adapter: str | None = None
    requested: str | None = None
    error: str | None = None
    available: list[str] | None = None


class AuthoringStatusOutput(StrictModel):
    enabled: bool
    adapter: str
    available_backends: list[str]


class SetConfigInput(StrictModel):
    title: str | None = None
    version: str | None = None
    adapter_type: str | None = None


class ConfigChangesOutput(StrictModel):
    adapter: str | None = None
    title: str | None = None
    version: str | None = None


class SetConfigOutput(StrictModel):
    updated: bool
    changes: ConfigChangesOutput = Field(default_factory=ConfigChangesOutput)
    requested: str | None = None
    error: str | None = None
    available: list[str] | None = None


class ResetRoutesOutput(StrictModel):
    reset: bool
    routes_cleared: int = Field(default=0, ge=0)
    error: str | None = None


__all__ = [
    "AddRouteInput", "AddRouteOutput", "AuthoringStatusOutput", "CapabilitiesOutput",
    "ConfigChangesOutput", "ConfigPropertyOutput", "ConfigSchemaOutput", "EmptyInput",
    "HealthOutput", "OpenAPISchemaOutput", "RemoveRouteInput", "RemoveRouteOutput",
    "ResetRoutesOutput", "RouteOutput", "RoutesOutput", "SetConfigInput", "SetConfigOutput",
    "StrictModel", "SwitchAdapterInput", "SwitchAdapterOutput",
]
