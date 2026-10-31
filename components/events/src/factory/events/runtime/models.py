import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, ConfigDict, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Envelope(BaseModel):
    """Standard context envelope for operational tools."""

    tenant_id: Optional[str] = Field(None, description="Multi-tenant isolation key")
    principal_id: Optional[str] = Field(None, description="Actor performing the action")
    session_id: Optional[str] = Field(None, description="User or agent session ID")
    request_id: Optional[str] = Field(None, description="Trace ID for the request")
    agent_id: Optional[str] = Field(None, description="Agent identifier if applicable")
    tool_name: Optional[str] = Field(None, description="Tool being executed")
    timestamp: datetime = Field(default_factory=utc_now)
    attributes: Dict[str, Union[str, int, float, bool]] = Field(default_factory=dict)

    model_config = ConfigDict(extra="ignore")


class Event(BaseModel):
    """The core atomic unit of the log."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=utc_now)
    source: str = Field(..., description="System or component emitting the event")
    type: str = Field(..., description="Classification (e.g., 'task.start', 'error')")
    payload: Dict[str, Any] = Field(
        default_factory=dict, description="Structured event data"
    )

    # Correlation context (denormalized from envelope for easier querying)
    trace_id: Optional[str] = None
    session_id: Optional[str] = None
    principal_id: Optional[str] = None


class EventFilter(BaseModel):
    """Criteria for querying events."""

    source: Optional[str] = None
    type: Optional[str] = None
    type_prefix: Optional[str] = None  # e.g. "task." matches "task.start"

    # Time range
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None

    # Correlation
    trace_id: Optional[str] = None
    session_id: Optional[str] = None

    limit: int = Field(100, ge=1, le=1000)
    offset: int = Field(0, ge=0)
    descending: bool = True  # Newest first by default


class EventQueryResult(BaseModel):
    events: List[Event]
    total_count: Optional[int] = None


class EventResult(BaseModel):
    """Result of publishing an event."""

    event_id: str
    status: str
    subscriptions_matched: int
    subscriptions_dispatched: int = 0
    timestamp: str
