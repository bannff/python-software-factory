"""Closed DTOs for Cache operational MCP tools."""
from __future__ import annotations

from pydantic import Field

from .base import StrictModel


class CacheKeyInput(StrictModel):
    key: str


class CacheSetInput(CacheKeyInput):
    value: str
    ttl_seconds: int | None = None


class CacheKeysInput(StrictModel):
    pattern: str = "*"


class CacheGetOutput(StrictModel):
    key: str
    value: str | None
    found: bool


class CacheSetOutput(StrictModel):
    key: str
    success: bool
    ttl: int | None


class CacheDeleteOutput(StrictModel):
    key: str
    deleted: bool


class CacheKeysOutput(StrictModel):
    pattern: str
    keys: list[str]
    count: int = Field(ge=0)


class CacheStatsOutput(StrictModel):
    hits: int = Field(ge=0)
    misses: int = Field(ge=0)
    hit_rate: float = Field(ge=0.0, le=1.0)
    size: int = Field(ge=0)
    max_size: int | None = Field(default=None, ge=0)


class CacheClearOutput(StrictModel):
    cleared: int = Field(ge=0)


class CacheExistsOutput(StrictModel):
    key: str
    exists: bool


class CacheTtlOutput(StrictModel):
    key: str
    ttl_seconds: int | None
    has_ttl: bool
