"""Strict public contracts for the Integrations MCP tools.

The legacy tools were declared with a bare decorator and no models, so the
gateway's public admission refused all of them (``input_model_not_concrete``):
listed by ``get_brick_tools`` but ``tool_not_found`` on call.
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, JsonValue

JsonObject = dict[str, JsonValue]


class DTO(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class EmptyInput(DTO):
    """Flat empty input for zero-argument tools."""


class ConnectorIdInput(DTO):
    connector_id: str


class CallInput(DTO):
    connector_id: str
    method: str
    path: str = ""
    params: JsonObject | None = None
    data: JsonValue = None
    headers: dict[str, str] | None = None


class RegisterInput(DTO):
    connector_id: str
    name: str
    base_url: str
    connector_type: str = "rest"
    headers: dict[str, str] | None = None
    timeout_seconds: int | None = None
    retry_count: int | None = None


class ObjectOutput(BaseModel):
    """A JSON object whose keys depend on the connector/runtime state."""

    model_config = ConfigDict(extra="allow")


class ConnectorOutput(DTO):
    connector: JsonObject | None


class ConnectorsOutput(DTO):
    connectors: list[JsonObject]


class ViewsOutput(DTO):
    views: list[JsonObject]


__all__ = [
    "CallInput", "ConnectorIdInput", "ConnectorOutput", "ConnectorsOutput",
    "DTO", "EmptyInput", "JsonObject", "ObjectOutput", "RegisterInput", "ViewsOutput",
]
