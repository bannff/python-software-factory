"""Bridge events to the in-process event_bus for live SSE streaming.

Fire-and-forget. Called from EventsRuntime.publish() so that swarm
lifecycle, game, and RL events reach the SSE endpoint in real time.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any


def bridge_to_event_bus(
    event_type: str,
    payload: dict[str, Any],
    source: str,
    timestamp: datetime,
) -> None:
    """Publish event to the in-process event_bus. Never raises."""
    try:
        from factory.mcp_utils.interface import event_bus
        event_bus.publish({
            "event_type": event_type,
            "source": source,
            "payload": payload,
            "ts": timestamp.timestamp(),
        })
    except Exception:
        pass  # fire-and-forget — never break publish()
