"""Context envelope for cross-module composition.

All operational tools accept this envelope to enable:
- Multi-tenancy
- Request correlation/tracing
- Audit logging
- Cross-module composition
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

# Envelope attribute limits
MAX_ATTRIBUTES = 32
MAX_ATTRIBUTE_KEY_LENGTH = 64
MAX_ATTRIBUTE_VALUE_LENGTH = 256
ALLOWED_ATTRIBUTE_TYPES = (str, int, float, bool)


@dataclass
class ContextEnvelope:
    """Common context envelope for operational tools.

    Enables clean composition across modules by providing
    consistent context for multi-tenancy, correlation, and audit.
    """

    # Multi-tenancy
    tenant_id: str | None = None
    principal_id: str | None = None

    # Session/request tracking
    session_id: str | None = None
    request_id: str | None = field(default_factory=lambda: str(uuid.uuid4()))
    correlation_id: str | None = None

    # UI-specific context
    view_id: str | None = None
    client_id: str | None = None

    # Agent context
    agent_id: str | None = None
    tool_name: str | None = None

    # Timing
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # Custom attributes (strict validation)
    attributes: dict[str, str | int | float | bool] = field(default_factory=dict)

    def __post_init__(self):
        """Validate attributes on creation."""
        self._validate_attributes()

    def _validate_attributes(self) -> None:
        """Validate attribute constraints."""
        if len(self.attributes) > MAX_ATTRIBUTES:
            raise ValueError(f"Too many attributes: {len(self.attributes)} > {MAX_ATTRIBUTES}")

        for key, value in self.attributes.items():
            if len(key) > MAX_ATTRIBUTE_KEY_LENGTH:
                raise ValueError(f"Attribute key too long: {len(key)} > {MAX_ATTRIBUTE_KEY_LENGTH}")

            if not isinstance(value, ALLOWED_ATTRIBUTE_TYPES):
                raise ValueError(f"Invalid attribute type for '{key}': {type(value).__name__}")

            if isinstance(value, str) and len(value) > MAX_ATTRIBUTE_VALUE_LENGTH:
                raise ValueError(
                    f"Attribute value too long for '{key}': "
                    f"{len(value)} > {MAX_ATTRIBUTE_VALUE_LENGTH}"
                )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "tenant_id": self.tenant_id,
            "principal_id": self.principal_id,
            "session_id": self.session_id,
            "request_id": self.request_id,
            "correlation_id": self.correlation_id,
            "view_id": self.view_id,
            "client_id": self.client_id,
            "agent_id": self.agent_id,
            "tool_name": self.tool_name,
            "timestamp": self.timestamp.isoformat(),
            "attributes": self.attributes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "ContextEnvelope":
        """Create from dictionary, handling None gracefully."""
        if not data:
            return cls()

        return cls(
            tenant_id=data.get("tenant_id"),
            principal_id=data.get("principal_id"),
            session_id=data.get("session_id"),
            request_id=data.get("request_id") or str(uuid.uuid4()),
            correlation_id=data.get("correlation_id"),
            view_id=data.get("view_id"),
            client_id=data.get("client_id"),
            agent_id=data.get("agent_id"),
            tool_name=data.get("tool_name"),
            timestamp=datetime.fromisoformat(data["timestamp"])
            if data.get("timestamp")
            else datetime.now(timezone.utc),
            attributes=data.get("attributes", {}),
        )

    def with_tool(self, tool_name: str) -> "ContextEnvelope":
        """Create a copy with tool_name set."""
        return ContextEnvelope(
            tenant_id=self.tenant_id,
            principal_id=self.principal_id,
            session_id=self.session_id,
            request_id=self.request_id,
            correlation_id=self.correlation_id,
            view_id=self.view_id,
            client_id=self.client_id,
            agent_id=self.agent_id,
            tool_name=tool_name,
            timestamp=self.timestamp,
            attributes=self.attributes.copy(),
        )
