from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


SCHEMA_VERSION = 1


class AuthoringSettings(BaseModel):
    enabled: bool = False


class PolicyStoreSettings(BaseModel):
    policies_subdir: str = "policies"


class CedarSettings(BaseModel):
    """Cedar policy evaluation settings."""

    enabled: bool = False
    policies_subdir: str = "cedar"


class Settings(BaseModel):
    schema_version: int = Field(default=SCHEMA_VERSION)
    service_name: str = "permissions-module"
    backend: Literal["filesystem"] = "filesystem"
    authoring: AuthoringSettings = Field(default_factory=AuthoringSettings)
    policy_store: PolicyStoreSettings = Field(default_factory=PolicyStoreSettings)
    cedar: CedarSettings = Field(default_factory=CedarSettings)


class Resource(BaseModel):
    type: str = Field(min_length=1, max_length=128)
    id: str | None = Field(default=None, max_length=256)
    owner: str | None = Field(default=None, max_length=256)
    tenant_id: str | None = Field(default=None, max_length=128)
    visibility: Literal["private", "team", "public"] | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)


class Condition(BaseModel):
    key: str = Field(min_length=1, max_length=256)
    op: Literal["eq", "ne", "in", "contains", "exists"]
    value: Any | None = None


class Rule(BaseModel):
    id: str = Field(min_length=1, max_length=128)
    effect: Literal["allow", "deny"]
    actions: list[str] = Field(default_factory=list)
    resource_types: list[str] = Field(default_factory=list)
    resource_ids: list[str] = Field(default_factory=list)
    conditions: list[Condition] = Field(default_factory=list)
    obligations: list[dict[str, Any]] = Field(default_factory=list)

    @field_validator("actions", "resource_types", "resource_ids")
    @classmethod
    def _nonempty_or_star(cls, v: list[str]) -> list[str]:
        if not isinstance(v, list):
            raise ValueError("must be a list")
        for item in v:
            if not isinstance(item, str) or not item.strip():
                raise ValueError("patterns must be non-empty strings")
        return v


class PolicyDefinition(BaseModel):
    schema_version: int = Field(default=SCHEMA_VERSION)
    id: str = Field(min_length=1, max_length=128)
    name: str = Field(min_length=1, max_length=256)
    version: str = Field(default="0.1", max_length=64)
    tags: list[str] = Field(default_factory=list)
    rules: list[Rule] = Field(default_factory=list)
