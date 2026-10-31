"""Strict Pydantic v2 contracts for Blueprint deterministic MCP tools."""
from __future__ import annotations

from .contracts_base import EmptyInput, JsonObject, JsonOutput, StrictInput


class CapabilitiesOutput(JsonOutput):
    name: str
    version: str
    type: str
    backends: list[str]
    features: list[str]
    services: list[str]


class ServiceHealthOutput(JsonOutput):
    healthy: bool
    url: str


class HealthOutput(JsonOutput):
    healthy: bool
    services: dict[str, ServiceHealthOutput]


class ConfigSchemaOutput(JsonOutput):
    type: str
    properties: JsonObject


class GetServiceUrlInput(StrictInput):
    service_name: str


class GetServiceUrlOutput(JsonOutput):
    found: bool
    service: str
    url: str | None = None
    error: str | None = None


class ListServicesOutput(JsonOutput):
    services: list[str]
    urls: dict[str, str]


class ServiceDefinitionOutput(JsonOutput):
    module: str
    construct: str
    alias: str


class SupportedServicesOutput(JsonOutput):
    services: dict[str, ServiceDefinitionOutput]


class ValidateSpecsInput(StrictInput):
    specs: list[JsonObject]


class ValidateSpecsOutput(JsonOutput):
    valid: bool
    resource_count: int
    services_used: list[str]
    vpc_required: bool
    errors: list[str]


__all__ = [
    "CapabilitiesOutput", "ConfigSchemaOutput", "EmptyInput", "GetServiceUrlInput",
    "GetServiceUrlOutput", "HealthOutput", "ListServicesOutput",
    "ServiceDefinitionOutput", "ServiceHealthOutput", "SupportedServicesOutput",
    "ValidateSpecsInput", "ValidateSpecsOutput",
]
