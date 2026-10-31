"""Session and steer model contract tests."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from factory.session.runtime.models import SessionRecord, SteerMessage, SteerState

NOW = datetime.now(timezone.utc)


def _session(**overrides):
    values = {
        "tenant_id": "tenant:local",
        "owner_id": "svc:local",
        "session_id": "session_1",
        "thread_id": "thread_1",
        "title": "Session",
        "agent_id": "companion-x-default",
        "model": "deepseek/deepseek-v4-flash",
        "created_at": NOW,
        "updated_at": NOW,
        "revision": 1,
    }
    values.update(overrides)
    return SessionRecord.model_validate(values)


def test_session_accepts_real_principal_identity_and_is_frozen() -> None:
    record = _session()
    assert record.owner_id == "svc:local"
    with pytest.raises(ValidationError):
        record.title = "changed"


def test_session_rejects_extra_and_control_character_identity() -> None:
    with pytest.raises(ValidationError):
        _session(extra="forbidden")
    with pytest.raises(ValidationError):
        _session(owner_id="bad\nowner")


def test_steer_rejects_invalid_send_id_and_oversized_content() -> None:
    base = {
        "tenant_id": "tenant:local", "owner_id": "svc:local",
        "session_id": "session_1", "delivery_id": "delivery_1",
        "send_id": "send_1", "content": "guide the active turn",
        "state": SteerState.WRITTEN, "created_at": NOW, "revision": 1,
    }
    with pytest.raises(ValidationError):
        SteerMessage.model_validate({**base, "send_id": "bad/id"})
    with pytest.raises(ValidationError):
        SteerMessage.model_validate({**base, "content": "x" * 32_769})


def test_steer_state_is_closed() -> None:
    assert {state.value for state in SteerState} == {
        "written", "consumed", "requeued",
    }
