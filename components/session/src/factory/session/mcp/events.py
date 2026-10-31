"""Content-free Session delivery events for AG-UI reconciliation."""
from __future__ import annotations

from typing import Any


def publish_steer(message: Any) -> None:
    """Publish identity and state only after a successful durable operation."""
    from factory.mcp_utils.interface import event_bus, get_envelope

    envelope = get_envelope() or {}
    correlation_id = envelope.get("correlation_id")
    payload = {
        "session_id": message.session_id,
        "delivery_id": message.delivery_id,
        "send_id": message.send_id,
        "state": message.state.value,
        "revision": message.revision,
    }
    if correlation_id:
        payload["correlation_id"] = str(correlation_id)
    event_bus.publish({
        "event_type": "session.steer", "source": "session",
        "payload": payload, "correlation_id": correlation_id,
    })


__all__ = ["publish_steer"]
