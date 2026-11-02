"""Pins the payload the Projects tab (``use-projects.ts``) sends to
``workflow.start_loop`` against the real input model and origin resolver."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from factory.mcp_utils.interface import reset_envelope, set_envelope
from factory.workflow.mcp.contracts.loops import StartLoopInput
from factory.workflow.mcp.loop_support import authority

# Mirrors the argument object built in frontends/next-dashboard/lib/hooks/use-projects.ts.
UI_PAYLOAD = {
    "kind": "goal", "agent_id": "companion-x-default", "objective": "UI sweep goal",
    "cycle_instructions": "Advance step", "interval_seconds": 300, "max_cycles": 24,
    "envelope": {"session_id": "thread-1"},
}


def test_ui_payload_is_accepted_and_carries_the_origin_thread() -> None:
    parsed = StartLoopInput.model_validate(UI_PAYLOAD)
    assert parsed.envelope is not None
    assert parsed.envelope.session_id == "thread-1"


def test_origin_key_is_session_id_not_thread_id() -> None:
    drifted = {**UI_PAYLOAD, "envelope": {"thread_id": "thread-1"}}
    with pytest.raises(ValidationError):
        StartLoopInput.model_validate(drifted)


def test_origin_thread_reaches_the_origin_resolver_as_session_id() -> None:
    token = set_envelope({"tenant_id": "t", "principal_id": "p"})
    try:
        context = authority(UI_PAYLOAD["envelope"])
        without = authority({})
    finally:
        reset_envelope(token)
    assert context.session_id == "thread-1"
    assert without.session_id is None
