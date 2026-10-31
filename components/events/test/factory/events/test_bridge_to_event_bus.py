from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

from factory.events.runtime.bridge import bridge_to_event_bus


@patch("factory.mcp_utils.interface.event_bus.publish")
def test_bridge_to_event_bus_preserves_rl_payload(mock_publish):
    payload = {
        "workflow_run_id": "run-42",
        "session_id": "session-42",
        "f1": 0.83,
    }
    timestamp = datetime(2026, 5, 13, tzinfo=timezone.utc)

    bridge_to_event_bus(
        event_type="rl.scored",
        payload=payload,
        source="games",
        timestamp=timestamp,
    )

    mock_publish.assert_called_once_with({
        "event_type": "rl.scored",
        "source": "games",
        "payload": payload,
        "ts": timestamp.timestamp(),
    })