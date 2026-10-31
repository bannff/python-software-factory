"""UI ports - Protocol interfaces for UI adapters.

Defines abstract interfaces that UI render adapters must implement.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol, runtime_checkable

from .models import UIComponent, UIView


@dataclass
class RenderResult:
    """Result of rendering a view through an adapter."""

    adapter_type: str
    content: Any
    content_type: str
    metadata: dict[str, Any] = field(default_factory=dict)
    rendered_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "adapter_type": self.adapter_type,
            "content": self.content,
            "content_type": self.content_type,
            "metadata": self.metadata,
            "rendered_at": self.rendered_at.isoformat(),
        }


@dataclass
class AdapterHealth:
    """Health status for a UI adapter."""

    healthy: bool
    adapter_type: str
    error: str | None = None


@runtime_checkable
class RenderPort(Protocol):
    """Port: UI render adapter (HTML, JSON, MCP-UI, etc.)"""

    @property
    def adapter_type(self) -> str:
        """Unique identifier for this adapter type."""
        ...

    @property
    def content_type(self) -> str:
        """Content type produced by this adapter."""
        ...

    def render_view(self, view: UIView) -> RenderResult:
        """Render a complete view."""
        ...

    def render_component(self, component: UIComponent) -> RenderResult:
        """Render a single component."""
        ...

    def supports_streaming(self) -> bool:
        """Whether this adapter supports streaming updates."""
        ...


@runtime_checkable
class PushChannelPort(Protocol):
    """Port: Real-time push channel (WebSocket, SSE, etc.)"""

    @property
    def channel_type(self) -> str:
        """Type identifier for this channel."""
        ...

    async def connect(self, client_id: str) -> bool:
        """Establish connection with a client."""
        ...

    async def disconnect(self, client_id: str) -> None:
        """Disconnect a client."""
        ...

    async def push(self, client_id: str, event: str, data: Any) -> bool:
        """Push an event to a connected client."""
        ...

    async def broadcast(self, event: str, data: Any) -> int:
        """Broadcast to all connected clients, return count."""
        ...
