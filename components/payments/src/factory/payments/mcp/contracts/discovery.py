"""Concrete public-safe discovery DTOs for Payments."""
from __future__ import annotations

from typing import Literal

from pydantic import Field

from .base import StrictModel


class ProviderCapability(StrictModel):
    """A provider the Payments domain can describe without credentials."""

    name: str
    type: Literal["mock", "stripe", "paypal"]
    description: str
    availability: Literal["available", "planned"]


class ConfigFieldDescriptor(StrictModel):
    """A machine-readable public registration-field descriptor."""

    type: Literal["string", "boolean", "object"]
    required: bool
    write_only: bool = Field(default=False, serialization_alias="writeOnly")
    format: Literal["secret"] | None = None


class ProviderConfigProjection(StrictModel):
    """Safe provider registration schema, deliberately excluding values."""

    name: ConfigFieldDescriptor
    provider_type: ConfigFieldDescriptor
    api_key: ConfigFieldDescriptor
    public_key: ConfigFieldDescriptor
    enabled: ConfigFieldDescriptor
    sandbox: ConfigFieldDescriptor
    options: ConfigFieldDescriptor


def provider_config_projection() -> ProviderConfigProjection:
    """Return the stable discovery projection rather than a runtime model schema."""
    return ProviderConfigProjection(
        name=ConfigFieldDescriptor(type="string", required=True),
        provider_type=ConfigFieldDescriptor(type="string", required=True),
        api_key=ConfigFieldDescriptor(type="string", required=False, write_only=True, format="secret"),
        public_key=ConfigFieldDescriptor(type="string", required=False, write_only=True, format="secret"),
        enabled=ConfigFieldDescriptor(type="boolean", required=False),
        sandbox=ConfigFieldDescriptor(type="boolean", required=False),
        options=ConfigFieldDescriptor(type="object", required=False),
    )


PROVIDER_CAPABILITIES = [
    ProviderCapability(name="mock", type="mock", description="In-memory provider for local development.", availability="available"),
    ProviderCapability(name="stripe", type="stripe", description="Stripe-shaped payment provider contract.", availability="available"),
    ProviderCapability(name="paypal", type="paypal", description="PayPal provider reserved for future implementation.", availability="planned"),
]
