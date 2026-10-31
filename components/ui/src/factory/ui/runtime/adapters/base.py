"""Base adapter protocol and types."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from ..models import UIComponent, UIView


@dataclass
class RenderResult:
    """Result of rendering a view through an adapter."""

    adapter_type: str
    content: Any  # The rendered output (format depends on adapter)
    content_type: str  # MIME type or format identifier
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


class RenderAdapter(ABC):
    """Base class for render adapters.

    Adapters transform UIView/UIComponent into target-specific formats.
    """

    @property
    @abstractmethod
    def adapter_type(self) -> str:
        """Unique identifier for this adapter type."""
        ...

    @property
    @abstractmethod
    def content_type(self) -> str:
        """Content type produced by this adapter."""
        ...

    @abstractmethod
    def render_view(self, view: UIView) -> RenderResult:
        """Render a complete view."""
        ...

    @abstractmethod
    def render_component(self, component: UIComponent) -> RenderResult:
        """Render a single component."""
        ...

    def supports_streaming(self) -> bool:
        """Whether this adapter supports streaming updates."""
        return False
