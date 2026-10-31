"""Configuration models for notification-module.

All configuration is Pydantic-validated for type safety.
"""
from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field


SCHEMA_VERSION = 1


class ServiceSettings(BaseModel):
    """Service identification."""
    name: str = Field(min_length=1)
    version: str | None = None


class AuthoringSettings(BaseModel):
    """Authoring tools configuration."""
    enabled: bool = False


class Settings(BaseModel):
    """Main settings file schema."""
    schema_version: int = Field(default=SCHEMA_VERSION)
    service: ServiceSettings
    default_channel: str | None = None
    authoring: AuthoringSettings = Field(default_factory=AuthoringSettings)


class ChannelConfig(BaseModel):
    """Notification channel configuration."""
    id: str = Field(min_length=1)
    type: Literal["console", "slack", "email", "webhook", "sms"]
    enabled: bool = True
    config: dict[str, Any] = Field(default_factory=dict)

    def sanitized(self) -> dict[str, Any]:
        """Return config without sensitive fields."""
        sensitive_keys = {"webhook_url", "api_key", "password", "secret", "token"}
        safe_config = {
            k: v for k, v in self.config.items()
            if k.lower() not in sensitive_keys
        }
        return {
            "id": self.id,
            "type": self.type,
            "enabled": self.enabled,
            "config": safe_config,
        }


class TemplateConfig(BaseModel):
    """Notification template configuration."""
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    subject: str | None = None
    body: str = Field(min_length=1)
    variables: list[str] = Field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        """Return template metadata."""
        return {
            "id": self.id,
            "name": self.name,
            "subject": self.subject,
            "variables": self.variables,
        }
