"""DTOs for authoring Workflow MCP tools."""
from __future__ import annotations

from .base import DTO, JsonObject


class AuthoringStatusOutput(DTO):
    enabled: bool
    config_dir: str
    allowed_paths: list[str] = []
    schema_versions: list[str] = []


class ValidateWorkflowsInput(DTO):
    dry_run: bool = True


class ValidationError(DTO):
    path: str
    error: str
    details: JsonObject | None = None


class ValidationOutput(DTO):
    ok: bool
    count: int
    errors: list[ValidationError]


class UpsertWorkflowInput(DTO):
    id: str
    yaml_or_object: str | JsonObject
    dry_run: bool = False


class DeleteWorkflowInput(DTO):
    id: str


class DefinitionOutput(DTO):
    ok: bool
    path: str
    dry_run: bool | None = None
    deleted: bool | None = None
