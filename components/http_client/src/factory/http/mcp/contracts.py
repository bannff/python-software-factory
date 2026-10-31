"""Strict same-brick DTOs for the HTTP MCP surface."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, JsonValue

JSONBody = dict[str, JsonValue]


class StrictModel(BaseModel):
    """Reject unknown fields and coercion at the public wire boundary."""

    model_config = ConfigDict(extra="forbid", strict=True)


class EmptyInput(StrictModel):
    pass


class GetInput(StrictModel):
    url: str
    headers: dict[str, str] | None = None
    params: dict[str, str] | None = None
    timeout: float = 30.0


class DeleteInput(StrictModel):
    url: str
    headers: dict[str, str] | None = None
    timeout: float = 30.0


class BodyInput(StrictModel):
    url: str
    body: JSONBody | str | None = None
    headers: dict[str, str] | None = None
    timeout: float = 30.0


class RequestInput(BodyInput):
    method: str
    params: dict[str, str] | None = None


class CapabilitiesFeaturesOutput(StrictModel):
    retry_logic: bool
    rate_limiting: bool
    auth_headers: bool
    timeout_handling: bool
    async_support: bool


class CapabilitiesOutput(StrictModel):
    name: str
    version: str
    backends: list[str]
    features: CapabilitiesFeaturesOutput


class ClientHealthOutput(StrictModel):
    healthy: bool
    backend: str


class HealthOutput(StrictModel):
    status: str
    clients: dict[str, ClientHealthOutput]
    error: str | None = None


class SchemaPropertyOutput(StrictModel):
    type: str
    description: str | None = None
    enum: list[str] | None = None
    default: str | float | int | list[int] | None = None


class ConfigGroupOutput(StrictModel):
    type: str
    properties: dict[str, SchemaPropertyOutput]


class ConfigSchemaOutput(StrictModel):
    client_config: ConfigGroupOutput
    retry_config: ConfigGroupOutput
    rate_limit_config: ConfigGroupOutput
    auth_config: ConfigGroupOutput


class BackendOutput(StrictModel):
    name: str
    description: str
    features: list[str]
    recommended_for: list[str]


class BackendsOutput(StrictModel):
    backends: list[BackendOutput]
    default: str
    available: list[str]


class HTTPResponseOutput(StrictModel):
    status_code: int
    headers: dict[str, str]
    body: str
    elapsed_ms: float
    ok: bool
