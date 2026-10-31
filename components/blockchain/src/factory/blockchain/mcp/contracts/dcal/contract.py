"""Strict, selector-free DCAL discovery DTOs for the future MCP surface."""
from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator

from .models import DcalDTO


class DcalCapabilities(DcalDTO):
    """Fixed capability declaration for the isolated dcal/v1 profile."""

    protocol: Literal["dcal"] = "dcal"
    version: Literal["v1"] = "v1"
    profile: Literal["dcal"] = "dcal"
    features: tuple[Literal["signed_operations", "trusted_binding"], ...] = Field(
        default=("signed_operations", "trusted_binding"), max_length=2,
    )


class DcalHealth(DcalDTO):
    """Safe health result shape that exposes no adapter or backend detail."""

    healthy: bool
    profile: Literal["dcal"] = "dcal"
    status: Literal["unconfigured", "ready", "degraded"]


class ConfigProperty(DcalDTO):
    """One bounded public configuration property description."""

    name: str = Field(min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9_]*$")
    value_type: Literal["string", "integer", "boolean"]
    required: bool


class DcalConfigSchema(DcalDTO):
    """Configuration description without accepting a profile selector ingress."""

    @field_validator("properties", mode="before")
    @classmethod
    def _reject_raw_properties(cls, value: object) -> object:
        if isinstance(value, (tuple, list)) and any(isinstance(item, dict) for item in value):
            raise ValueError("properties must be ConfigProperty instances")
        return value

    protocol: Literal["dcal"] = "dcal"
    version: Literal["v1"] = "v1"
    properties: tuple[ConfigProperty, ...] = Field(max_length=32)


__all__ = ["ConfigProperty", "DcalCapabilities", "DcalConfigSchema", "DcalHealth"]
