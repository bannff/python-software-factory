"""Strict authoring Permissions MCP DTOs."""
from __future__ import annotations

import re
from pydantic import Field, JsonValue, field_validator

from .base import JsonObject, OutputModel, StrictModel, _MAX_LIST_ITEMS, bounded_json

_ID_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,127}$")
_MAX_YAML_TEXT = 65_536


def _relative_path(value: str | None) -> str | None:
    if value is not None and (value.startswith(("/", "\\")) or ".." in value.replace("\\", "/").split("/")):
        raise ValueError("paths must be logical relative paths")
    return value


class AuthoringStatusOutput(OutputModel):
    enabled: bool
    config_dir: str | None = Field(default=None, max_length=64)
    allowed_paths: list[str] = Field(default_factory=list, max_length=16)
    schema_versions: list[int] = Field(default_factory=list, max_length=16)

    @field_validator("config_dir")
    @classmethod
    def _config_path_is_logical(cls, value: str | None) -> str | None:
        return _relative_path(value)

    @field_validator("allowed_paths")
    @classmethod
    def _allowed_paths_are_logical(cls, value: list[str]) -> list[str]:
        return [_relative_path(item) or "" for item in value]


class ValidationDetailOutput(OutputModel):
    location: str = Field(min_length=1, max_length=256)
    type: str = Field(min_length=1, max_length=64)
    message: str = Field(min_length=1, max_length=128)


class PolicyValidationIssue(OutputModel):
    path: str = Field(min_length=1, max_length=256)
    error: str = Field(min_length=1, max_length=64)
    details: list[ValidationDetailOutput] = Field(default_factory=list, max_length=8)

    @field_validator("path")
    @classmethod
    def _issue_path_is_logical(cls, value: str) -> str:
        return _relative_path(value) or "policies/unknown.yaml"


class ValidatePoliciesOutput(OutputModel):
    ok: bool
    count: int = Field(ge=0, le=_MAX_LIST_ITEMS)
    errors: list[PolicyValidationIssue] = Field(default_factory=list, max_length=_MAX_LIST_ITEMS)


class PolicyIdInput(StrictModel):
    id: str = Field(min_length=1, max_length=128)

    @field_validator("id")
    @classmethod
    def _valid_id(cls, value: str) -> str:
        if _ID_RE.fullmatch(value) is None or any(ord(char) < 32 or ord(char) == 127 for char in value):
            raise ValueError("id must match [a-zA-Z0-9][a-zA-Z0-9_-]{0,127}")
        return value


class UpsertPolicyInput(PolicyIdInput):
    yaml_or_object: str | JsonObject
    dry_run: bool = False

    @field_validator("yaml_or_object")
    @classmethod
    def _bounded_policy_payload(cls, value: str | JsonObject) -> str | JsonObject:
        if isinstance(value, str):
            if len(value.encode("utf-8")) > _MAX_YAML_TEXT:
                raise ValueError("yaml_or_object string is too large")
            bounded_json(value, label="yaml_or_object")
            return value
        if not isinstance(value, dict):
            raise ValueError("yaml_or_object must be a YAML string or JSON object")
        bounded_json(value, label="yaml_or_object")
        return value


class UpsertPolicyOutput(OutputModel):
    ok: bool
    dry_run: bool
    path: str | None = Field(default=None, max_length=256)
    error: str | None = Field(default=None, max_length=64)

    @field_validator("path")
    @classmethod
    def _upsert_path_is_logical(cls, value: str | None) -> str | None:
        return _relative_path(value)


class DeletePolicyOutput(OutputModel):
    ok: bool
    deleted: bool
    path: str | None = Field(default=None, max_length=256)
    error: str | None = Field(default=None, max_length=64)

    @field_validator("path")
    @classmethod
    def _delete_path_is_logical(cls, value: str | None) -> str | None:
        return _relative_path(value)


__all__ = [
    "AuthoringStatusOutput", "DeletePolicyOutput", "PolicyIdInput", "PolicyValidationIssue",
    "UpsertPolicyInput", "UpsertPolicyOutput", "ValidatePoliciesOutput", "ValidationDetailOutput",
]
