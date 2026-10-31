"""Closed DTOs for Cache deterministic MCP tools."""
from __future__ import annotations

from pydantic import Field

from .base import CacheHealthOutput, StrictModel


class CapabilitiesOutput(StrictModel):
    name: str = Field(max_length=64)
    version: str = Field(max_length=32)
    backends: list[str] = Field(max_length=16)
    features: list[str] = Field(max_length=16)


class HealthOutput(StrictModel):
    healthy: bool
    caches: dict[str, CacheHealthOutput] = Field(max_length=64)


class DescribeConfigSchemaOutput(StrictModel):
    type: str = Field(max_length=32)
    properties: dict[str, ConfigOptionOutput] = Field(max_length=16)


class ConfigOptionOutput(StrictModel):
    type: str = Field(max_length=32)
    description: str = Field(max_length=256)
    enum: list[str] | None = Field(default=None, max_length=16)
