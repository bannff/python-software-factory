"""AG-UI protocol render adapter.

Translates internal events and views into AG-UI protocol events
for streaming to AG-UI-compatible frontends.
"""

from __future__ import annotations

from typing import Any

from .base import RenderAdapter, RenderResult
from ..models import UIComponent, UIView
from ..ag_ui_mapper import (
    AGUIEventType,
    make_state_delta,
    make_state_snapshot,
    map_event,
)


class AGUIAdapter(RenderAdapter):
    """Adapter that outputs AG-UI protocol events.

    Unlike HTMX/React/Flet adapters that produce rendered markup,
    this adapter produces AG-UI event dicts for SSE streaming.
    """

    @property
    def adapter_type(self) -> str:
        return "ag-ui"

    @property
    def content_type(self) -> str:
        return "text/event-stream"

    def render_view(self, view: UIView) -> RenderResult:
        """Render a view as an AG-UI MESSAGES_SNAPSHOT event."""
        snapshot = {
            "type": AGUIEventType.MESSAGES_SNAPSHOT,
            "messages": [
                {"id": view.id, "role": "assistant", "content": view.name},
            ],
        }
        return RenderResult(
            adapter_type=self.adapter_type,
            content=snapshot,
            content_type=self.content_type,
            metadata={"ag_ui": True, "view_id": view.id},
        )

    def render_component(self, component: UIComponent) -> RenderResult:
        """Render a component as an AG-UI CUSTOM event."""
        event = {
            "type": AGUIEventType.CUSTOM,
            "name": "component",
            "value": component.to_dict(),
        }
        return RenderResult(
            adapter_type=self.adapter_type,
            content=event,
            content_type=self.content_type,
            metadata={"ag_ui": True},
        )

    def supports_streaming(self) -> bool:
        """AG-UI is a streaming protocol."""
        return True

    def render_event(self, internal_event: dict[str, Any]) -> list[dict]:
        """Translate an internal event to AG-UI events.

        Args:
            internal_event: Internal event dict with 'type' and 'payload'.

        Returns:
            List of AG-UI event dicts.
        """
        return map_event(internal_event)

    def render_state_snapshot(self, state: dict[str, Any]) -> dict:
        """Produce a STATE_SNAPSHOT AG-UI event.

        Args:
            state: Full state dict to snapshot.

        Returns:
            AG-UI STATE_SNAPSHOT event dict.
        """
        return make_state_snapshot(state)

    def render_state_delta(self, patch: list[dict]) -> dict:
        """Produce a STATE_DELTA AG-UI event (JSON Patch RFC 6902).

        Args:
            patch: List of JSON Patch operations.

        Returns:
            AG-UI STATE_DELTA event dict.
        """
        return make_state_delta(patch)
