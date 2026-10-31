"""Strict Connections MCP ingress and egress DTOs (no secret values ever egress)."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from factory.mcp_utils.interface import WireDatetime

from ..runtime.models import ServerSpec


class DTO(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class EnvelopeInput(DTO):
    tenant_id: str | None = None
    principal_id: str | None = None
    session_id: str | None = None
    thread_id: str | None = None


class ListServersInput(DTO):
    envelope: EnvelopeInput | None = None


class AddServerInput(DTO):
    name: str = Field(min_length=1, max_length=64)
    spec: ServerSpec
    envelope: EnvelopeInput | None = None


class ImportServersInput(DTO):
    """Paste of a standard ``{"mcpServers": {...}}`` document as JSON text."""

    document: str = Field(min_length=2, max_length=65_536)
    envelope: EnvelopeInput | None = None


class UpdateServerInput(DTO):
    name: str = Field(min_length=1, max_length=64)
    spec: ServerSpec
    expected_revision: int = Field(ge=1)
    envelope: EnvelopeInput | None = None


class RemoveServerInput(DTO):
    name: str = Field(min_length=1, max_length=64)
    expected_revision: int = Field(ge=1)
    envelope: EnvelopeInput | None = None


class ReloadInput(DTO):
    envelope: EnvelopeInput | None = None


class ServerView(DTO):
    """Public projection: env/header VALUES are never present — both sides of
    ``env``/``headers`` are environment-variable NAMES (target -> source)."""

    name: str
    transport: str
    command: str | None
    args: list[str]
    cwd: str | None
    env: dict[str, str]
    url: str | None
    headers: dict[str, str]
    enabled: bool
    mounted: bool
    unresolved_env: list[str]
    tools_count: int
    revision: int
    created_at: WireDatetime
    updated_at: WireDatetime


class ServersOutput(DTO):
    servers: list[ServerView]


class ServerOutput(DTO):
    server: ServerView


class RemovedOutput(DTO):
    removed: bool
    name: str


class ReloadOutput(DTO):
    outcome: dict[str, str]


__all__ = [
    "AddServerInput", "EnvelopeInput", "ImportServersInput", "ListServersInput",
    "ReloadInput", "ReloadOutput", "RemoveServerInput", "RemovedOutput",
    "ServerOutput", "ServerView", "ServersOutput", "UpdateServerInput",
]


class ComputerUseStatusInput(DTO):
    """No arguments: pure detection over mounted servers."""


class ComputerUseStatusOutput(DTO):
    platform_supported: bool
    mounted: bool
    server_name: str | None
    tool_names: list[str]
    preset_name: str
    preset_command: str
    preset_args: list[str]
    preset_command_found: bool
    preset_command_path: str | None
    accessibility_hint: str
