"""Strict DTOs for deterministic Browser MCP tools."""
from __future__ import annotations

from .base import DTO, EmptyInput, JsonObject, SessionOutput


class CapabilitiesInput(EmptyInput):
    pass


class CapabilitiesOutput(DTO):
    name: str
    version: str
    tools: dict[str, list[str]]
    adapters: list[str]
    features: list[str]


class HealthCheckInput(EmptyInput):
    pass


class HealthCheckOutput(DTO):
    healthy: bool
    adapter: JsonObject
    active_sessions: int


class ConfigSchemaInput(EmptyInput):
    pass


class ConfigSchemaOutput(DTO):
    type: str
    properties: JsonObject


class ListSessionsInput(EmptyInput):
    pass


class ListSessionsOutput(DTO):
    count: int
    sessions: list[SessionOutput]


class GetSessionInput(DTO):
    session_id: str


class GetSessionOutput(DTO):
    found: bool
    session: SessionOutput | None = None
    reason: str | None = None


class EngineStatusInput(EmptyInput):
    pass


class EngineStatusOutput(DTO):
    """Pure detection: what the process would use and whether CDP could work."""

    engine: str
    available_engines: list[str]
    chrome_path: str | None
    chrome_found: bool
    websockets_available: bool
    change_hint: str
