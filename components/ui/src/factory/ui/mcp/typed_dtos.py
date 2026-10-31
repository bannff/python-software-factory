"""Strict Pydantic v2 DTOs for deterministic and A2UI UI MCP tools."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class _DTO(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, serialize_by_alias=True)


class EmptyInput(_DTO):
    pass


class ThemeInfoInput(_DTO):
    framework: str = "all"


class A2UIPayloadInput(_DTO):
    payload: dict[str, Any]


class RenderA2UIInput(A2UIPayloadInput):
    backend: str = "htmx"
    view_name: str = "A2UI View"


class A2UIToViewInput(A2UIPayloadInput):
    view_id: str | None = None
    view_name: str = "A2UI View"
    save: bool = False


class ViewIdInput(_DTO):
    view_id: str


class CapabilitiesOutput(_DTO):
    module: str
    version: str
    schema_version: str
    running_mode: str
    authoring_enabled: bool
    adapters: dict[str, Any]
    storage: dict[str, Any]
    push: dict[str, Any]
    limits: dict[str, Any]
    feature_flags: dict[str, Any]
    component_types: list[str]


class HealthOutput(_DTO):
    status: str
    checks: dict[str, Any] | None = None
    uptime_seconds: float | None = None
    started_at: str | None = None
    last_error: str | None = None


class ConfigSchemaOutput(_DTO):
    schema_url: str = Field(alias="$schema")
    title: str
    type: str
    properties: dict[str, Any]


class ViewRegistryOutput(_DTO):
    views: list[dict[str, Any]]
    total: int
    config_dir: str


class ComponentRegistryOutput(_DTO):
    components: list[dict[str, Any]]


class AdaptersOutput(_DTO):
    adapters: list[dict[str, Any]]
    default: str
    recommendations: dict[str, str] | None = None


class ThemeInfoOutput(_DTO):
    daisyui: dict[str, Any] | None = None
    shadcn: dict[str, Any] | None = None


class A2UIComponentCatalogOutput(_DTO):
    components: list[dict[str, Any]]
    version: str
    protocol: str
    reference: str


class A2UIValidationOutput(_DTO):
    valid: bool
    errors: list[dict[str, Any]]
    component_count: int


class A2UIRenderOutput(_DTO):
    content: Any
    content_type: str
    adapter: str
    metadata: dict[str, Any]


class A2UIViewOutput(_DTO):
    view: dict[str, Any]
    saved: bool
    component_count: int


class ViewA2UIOutput(_DTO):
    components: list[dict[str, Any]]
    version: str
    metadata: dict[str, Any]
