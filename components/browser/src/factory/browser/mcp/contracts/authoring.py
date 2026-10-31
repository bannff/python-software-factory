"""Strict DTOs for Browser authoring MCP tools."""
from __future__ import annotations

from .base import DTO, EmptyInput, JsonObject, JsonValue, _validate_json


class AuthoringStatusInput(EmptyInput):
    pass


class AuthoringStatusOutput(DTO):
    enabled: bool
    config_dir: str | None = None
    allowed_paths: list[str] = []
    message: str | None = None


class ListProfilesInput(EmptyInput):
    pass


class ProfileOutput(DTO):
    id: str
    path: str
    config: JsonValue = None
    error: str | None = None


class ListProfilesOutput(DTO):
    profiles: list[ProfileOutput]
    count: int


class UpsertProfileInput(DTO):
    id: str
    config: JsonObject
    dry_run: bool = False


class UpsertProfileOutput(DTO):
    ok: bool
    dry_run: bool
    path: str


class DeleteProfileInput(DTO):
    id: str


class DeleteProfileOutput(DTO):
    ok: bool
    deleted: bool
    path: str


def json_safe_profile(value: JsonValue) -> JsonValue:
    """Validate a persisted profile configuration before transport."""

    return _validate_json(value)
