"""Strict typed boundaries for UI operational MCP tools."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, JsonValue, StrictBool, StrictFloat, StrictInt, StrictStr


class _Input(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class _Output(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class ContextEnvelopeInput(_Input):
    tenant_id: StrictStr | None = None
    principal_id: StrictStr | None = None
    session_id: StrictStr | None = None
    request_id: StrictStr | None = None
    correlation_id: StrictStr | None = None
    view_id: StrictStr | None = None
    client_id: StrictStr | None = None
    agent_id: StrictStr | None = None
    tool_name: StrictStr | None = None
    timestamp: StrictStr | None = None
    attributes: dict[StrictStr, StrictStr | StrictInt | StrictFloat | StrictBool] = Field(default_factory=dict)


class _EnvelopeInput(_Input):
    envelope: ContextEnvelopeInput | None = None


class ListViewsInput(_EnvelopeInput):
    pass


class GetViewInput(_EnvelopeInput):
    view_id: StrictStr
    adapter: StrictStr = "json"
    route: StrictStr | None = None


class PushChannelStatusInput(_EnvelopeInput):
    pass


class ViewHistoryInput(_EnvelopeInput):
    view_id: StrictStr | None = None
    limit: StrictInt = 50


class ConnectClientInput(_EnvelopeInput):
    client_id: StrictStr
    subscribe_to: list[StrictStr] | None = None


class DisconnectClientInput(_EnvelopeInput):
    client_id: StrictStr


class SubscribeInput(_EnvelopeInput):
    client_id: StrictStr
    view_id: StrictStr


class _RequestOutput(_Output):
    request_id: str | None


class ViewSummary(_Output):
    id: str
    name: str
    component_count: int
    version: int
    updated_at: str


class ListViewsOutput(_RequestOutput):
    views: list[ViewSummary]
    total: int


class RenderedViewOutput(_RequestOutput):
    adapter_type: str
    content: JsonValue
    content_type: str
    metadata: dict[str, JsonValue]
    rendered_at: str


class ClientConnectionOutput(_Output):
    client_id: str
    channel_type: str
    subscribed_views: list[str]
    connected_at: str
    last_activity: str
    metadata: dict[str, JsonValue]


class PushChannelStatusOutput(_RequestOutput):
    connected_clients: int
    clients: list[ClientConnectionOutput]


class ViewUpdateOutput(_Output):
    view_id: str
    action: str
    payload: dict[str, JsonValue]
    version: int
    timestamp: str


class ViewHistoryOutput(_RequestOutput):
    updates: list[ViewUpdateOutput]
    count: int


class ConnectClientOutput(_RequestOutput):
    connected: bool
    client_id: str
    subscribed_to: list[str]


class DisconnectClientOutput(_RequestOutput):
    disconnected: bool
    client_id: str


class SubscribeOutput(_RequestOutput):
    subscribed: bool
    client_id: str
    view_id: str
