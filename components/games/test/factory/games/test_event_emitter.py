from __future__ import annotations

from unittest.mock import MagicMock, patch

from factory.games.runtime import event_emitter


@patch("factory.games.runtime.event_emitter._get_invoker")
def test_emit_publishes_games_event_with_payload(mock_get_invoker):
    invoker = MagicMock()
    mock_get_invoker.return_value = invoker

    payload = {
        "workflow_run_id": "run-42",
        "session_id": "session-42",
        "f1": 0.83,
    }

    event_emitter.emit("rl.scored", payload)

    assert invoker.call_count == 1
    _, kwargs = invoker.call_args
    assert kwargs["source"] == "games"
    assert kwargs["event_type"] == "rl.scored"
    # games owns its own run_id (aliased from workflow_run_id) and must
    # declare authority explicitly — this is the bd:python-factory-1j2fe /
    # issue #734 fix: no more implicit source=="workflow" allowlist.
    assert kwargs["run_id_authoritative"] is True
    assert kwargs["payload"]["run_id"] == "run-42"
    assert kwargs["payload"]["f1"] == 0.83


@patch("factory.games.runtime.event_emitter._get_invoker")
def test_emit_does_not_claim_authority_without_run_id(mock_get_invoker):
    invoker = MagicMock()
    mock_get_invoker.return_value = invoker

    event_emitter.emit("rl.started", {"session_id": "session-42"})

    _, kwargs = invoker.call_args
    assert kwargs["run_id_authoritative"] is False


@patch("factory.games.runtime.event_emitter._get_invoker")
def test_emit_logs_error_when_events_publish_fails(mock_get_invoker, caplog):
    """A real events_publish failure (e.g. the correlation conflict this bug
    was about) must be loud, not swallowed at warning level."""
    import logging

    invoker = MagicMock(side_effect=ValueError("conflicting run_id/workflow_run_id"))
    mock_get_invoker.return_value = invoker

    with caplog.at_level(logging.ERROR, logger="factory.games.runtime.event_emitter"):
        event_emitter.emit("rl.scored", {"run_id": "run-42"})

    assert any(
        record.levelno >= logging.ERROR for record in caplog.records
    ), "events_publish failure must be logged at ERROR, not swallowed as a warning"