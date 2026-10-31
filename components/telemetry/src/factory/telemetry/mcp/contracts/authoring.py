"""DTOs for authoring Telemetry MCP tools."""
from __future__ import annotations

from .base import DTO, JsonObject


class AuthoringStatusOutput(DTO):
    enabled: bool
    config_dir: str
    env_var: str


class ListConfigsInput(DTO):
    kind: str


class ConfigListOutput(DTO):
    configs: list[JsonObject]


class ReadConfigInput(DTO):
    kind: str
    item_id: str


class ReadConfigOutput(DTO):
    ok: bool
    kind: str | None = None
    id: str | None = None
    config: JsonObject | list[JsonObject] | None = None
    error: str | None = None


class WriteConfigInput(DTO):
    kind: str
    config: JsonObject


class WriteMetricFileInput(DTO):
    file_id: str
    definitions: list[JsonObject]


class MutationOutput(DTO):
    ok: bool
    kind: str | None = None
    id: str | None = None
    path: str | None = None
    error: str | None = None
