"""Pydantic model for an event history entry."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


class EventHistoryEntry(BaseModel):
    """An entry in the event history."""

    event_id: str = Field(..., description="Unique event identifier")
    event_type: str = Field(..., description="Type of the event")
    payload: dict[str, Any] = Field(..., description="Event payload")
    source: str = Field(..., description="Source of the event")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When the event occurred",
    )
    tenant_id: str | None = Field(default=None, description="Tenant ID")
    principal_id: str | None = Field(default=None, description="Principal ID")
    correlation_id: str | None = Field(default=None, description="Correlation ID")
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata",
    )

    model_config = {"extra": "forbid"}
