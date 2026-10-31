"""Context envelope for cross-module composition."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


class ContextEnvelope(BaseModel):
    """Common context envelope for operational tools.

    Provides consistent context across module boundaries for:
    - Multi-tenancy support
    - Request correlation
    - Audit trails
    - Session tracking
    """

    tenant_id: str | None = Field(
        default=None,
        description="Tenant identifier for multi-tenant scenarios",
    )
    principal_id: str | None = Field(
        default=None,
        description="Principal (user/service) identifier",
    )
    session_id: str | None = Field(
        default=None,
        description="Session identifier for tracking",
    )
    request_id: str | None = Field(
        default=None,
        description="Request/correlation ID for tracing",
    )
    agent_id: str | None = Field(
        default=None,
        description="Agent identifier if invoked by an agent",
    )
    tool_name: str | None = Field(
        default=None,
        description="Name of the tool being invoked",
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp of the request",
    )
    attributes: dict[str, str | int | float | bool] = Field(
        default_factory=dict,
        description="Additional attributes (strict types, size-limited)",
    )

    model_config = {"extra": "forbid"}
