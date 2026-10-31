"""Pydantic models for integrations brick."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field, HttpUrl

from factory.integrations.core import SCHEMA_VERSION, ConnectorStatus, ConnectorType


def _utcnow() -> datetime:
    """Get current UTC time (timezone-aware)."""
    return datetime.now(timezone.utc)


class ConnectorConfig(BaseModel):
    """Configuration for a connector."""

    id: str = Field(min_length=1, max_length=128)
    name: str = Field(min_length=1, max_length=256)
    connector_type: ConnectorType
    base_url: str = Field(min_length=1)
    headers: dict[str, str] = Field(default_factory=dict)
    timeout_seconds: int = Field(default=30, ge=1, le=300)
    retry_count: int = Field(default=3, ge=0, le=10)
    rate_limit_per_minute: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class Connector(BaseModel):
    """A registered connector instance."""

    config: ConnectorConfig
    status: ConnectorStatus = ConnectorStatus.DISCONNECTED
    last_used: datetime | None = None
    error_message: str | None = None
    request_count: int = 0
    error_count: int = 0


class RequestResult(BaseModel):
    """Result of an API request."""

    success: bool
    status_code: int | None = None
    data: Any = None
    error: str | None = None
    latency_ms: float = 0.0
    connector_id: str = ""


class ConnectorHealth(BaseModel):
    """Health status for integrations runtime."""

    healthy: bool
    connector_count: int = 0
    connected_count: int = 0
    error_count: int = 0
    latency_ms: float = 0.0
    message: str = ""


class AuthoringSettings(BaseModel):
    """Authoring mode settings."""

    enabled: bool = False


class Settings(BaseModel):
    """Integrations brick configuration."""

    schema_version: int = Field(default=SCHEMA_VERSION)
    service_name: str = "integrations-module"
    default_timeout_seconds: int = 30
    default_retry_count: int = 3
    authoring: AuthoringSettings = Field(default_factory=AuthoringSettings)
