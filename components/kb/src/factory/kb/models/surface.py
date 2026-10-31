"""Pydantic boundary models for KB deterministic and authoring MCP tools."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, JsonValue


class KbEmptyRequest(BaseModel):
    schema_version: Literal["v1"] = "v1"


class KbCapabilitiesResult(BaseModel):
    schema_version: Literal[1] = 1
    features: list[str]
    tooling: dict[str, list[str]]
    details: dict[str, JsonValue]


class KbHealthResult(BaseModel):
    schema_version: Literal["v1"] = "v1"
    status: Literal["ok", "error"]
    details: dict[str, JsonValue]


class KbConfigSchemaResult(BaseModel):
    schema_version: Literal[1] = 1
    config_schema: dict[str, JsonValue]
    domain_schemas: dict[str, JsonValue]


class KbCollectionSummary(BaseModel):
    id: str
    name: str


class KbCollectionRegistryResult(BaseModel):
    schema_version: Literal["v1"] = "v1"
    collections: list[KbCollectionSummary] = Field(default_factory=list)
    total: int = Field(default=0, ge=0)


class KbCollectionStatsRequest(BaseModel):
    schema_version: Literal["v1"] = "v1"
    collection_id: str | None = Field(default=None, min_length=1, max_length=128)


class KbCollectionStatsResult(BaseModel):
    schema_version: Literal["v1"] = "v1"
    collection_id: str | None = None
    document_count: int = Field(ge=0)
    total_size_bytes: int = Field(ge=0)


class KbAuthoringStatusResult(BaseModel):
    schema_version: Literal["v1"] = "v1"
    enabled: bool
    config_dir: str
    collections_dir: str
    env_var: str


class KbAuthoringValidateRequest(BaseModel):
    schema_version: Literal["v1"] = "v1"
    dry_run: bool = True


class KbAuthoringUpsertRequest(BaseModel):
    schema_version: Literal["v1"] = "v1"
    collection_id: str = Field(min_length=1, max_length=128)
    collection_data: dict[str, JsonValue]
    dry_run: bool = False


class KbAuthoringDeleteRequest(BaseModel):
    schema_version: Literal["v1"] = "v1"
    collection_id: str = Field(min_length=1, max_length=128)


class KbAuthoringResult(BaseModel):
    schema_version: Literal["v1"] = "v1"
    ok: bool
    error: str | None = None
    valid: int | None = Field(default=None, ge=0)
    errors: list[JsonValue] = Field(default_factory=list)
    dry_run: bool | None = None
    would_write: str | None = None
    path: str | None = None
    deleted: str | None = None
    details: JsonValue | None = None


__all__ = [
    "KbAuthoringDeleteRequest",
    "KbAuthoringResult",
    "KbAuthoringStatusResult",
    "KbAuthoringUpsertRequest",
    "KbAuthoringValidateRequest",
    "KbCapabilitiesResult",
    "KbCollectionRegistryResult",
    "KbCollectionStatsRequest",
    "KbCollectionStatsResult",
    "KbConfigSchemaResult",
    "KbEmptyRequest",
    "KbHealthResult",
]
