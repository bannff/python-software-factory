"""Tests for the ``StateDeltaEvent`` handler in ``ag_ui_mapper_chat`` (bd-D).

Verifies the chat-stream → AG-UI translation of canvas paint events.
First emission per turn produces ``STATE_SNAPSHOT`` (seeds
``state.canvas={}`` per JSON Patch RFC 6902 discipline); subsequent
emissions produce ``STATE_DELTA`` with ``replace`` ops on
``/canvas/<target>``.

Hard pre-conditions verified here (meta-architect verdict
``2dabeff1-eee0-47cc-9d98-1165ebc88e96`` Q10):
- ``canvas_seeded`` resets per-turn (via fresh ``AGUIStreamState``).
- ``STATE_DELTA`` never emitted before ``STATE_SNAPSHOT`` seeds canvas.
- ``replace`` op (not ``add``) is used for slot updates.
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings, strategies as st

from factory.agent.runtime.models import StateDeltaEvent, DoneEvent
from factory.ui.runtime.ag_ui_mapper import AGUIEventType
from factory.ui.runtime.ag_ui_mapper_chat import (
    AGUIStreamState,
    map_chat_stream_event,
)


_PAYLOAD = {"components": [{"id": "n1", "type": "card", "props": {}}],
            "name": "graph"}


# --- mode='snapshot' → STATE_SNAPSHOT seeds the canvas ---------------------


def test_snapshot_mode_emits_state_snapshot_with_seed():
    """First paint of a slot — emit STATE_SNAPSHOT carrying ``canvas`` object."""
    state = AGUIStreamState()
    event = StateDeltaEvent(target="graph", mode="snapshot", payload=_PAYLOAD)
    out = map_chat_stream_event(event, state)
    assert len(out) == 1
    assert out[0]["type"] == AGUIEventType.STATE_SNAPSHOT
    assert out[0]["snapshot"] == {"canvas": {"graph": _PAYLOAD}}
    assert "timestamp" in out[0]
    assert state.canvas_seeded is True


def test_first_paint_uses_snapshot_even_if_mode_is_delta():
    """JSON Patch ``replace`` on a missing parent silently no-ops on the FE.
    The mapper MUST seed first regardless of explicit mode."""
    state = AGUIStreamState()
    event = StateDeltaEvent(target="findings", mode="delta", payload=_PAYLOAD)
    out = map_chat_stream_event(event, state)
    assert len(out) == 1
    assert out[0]["type"] == AGUIEventType.STATE_SNAPSHOT
    assert out[0]["snapshot"] == {"canvas": {"findings": _PAYLOAD}}
    assert state.canvas_seeded is True


def test_subsequent_delta_emits_state_delta_replace():
    """After seeding, mode='delta' emits a JSON Patch replace op."""
    state = AGUIStreamState()
    state.canvas_seeded = True  # simulate prior snapshot
    event = StateDeltaEvent(target="timeline", mode="delta", payload=_PAYLOAD)
    out = map_chat_stream_event(event, state)
    assert len(out) == 1
    assert out[0]["type"] == AGUIEventType.STATE_DELTA
    assert out[0]["delta"] == [
        {"op": "replace", "path": "/canvas/timeline", "value": _PAYLOAD},
    ]


def test_subsequent_snapshot_emits_state_snapshot():
    """Explicit re-snapshot after seeding still produces STATE_SNAPSHOT."""
    state = AGUIStreamState()
    state.canvas_seeded = True
    event = StateDeltaEvent(target="graph", mode="snapshot", payload=_PAYLOAD)
    out = map_chat_stream_event(event, state)
    assert out[0]["type"] == AGUIEventType.STATE_SNAPSHOT


# --- canvas_seeded transitions --------------------------------------------


def test_canvas_seeded_transitions_false_to_true():
    state = AGUIStreamState()
    assert state.canvas_seeded is False
    event = StateDeltaEvent(target="graph", mode="snapshot", payload=_PAYLOAD)
    map_chat_stream_event(event, state)
    assert state.canvas_seeded is True


def test_canvas_seeded_resets_per_turn_via_fresh_state():
    """Per pre-condition (iv): fresh AGUIStreamState per stream resets seed."""
    state1 = AGUIStreamState()
    map_chat_stream_event(
        StateDeltaEvent(target="graph", mode="snapshot", payload=_PAYLOAD),
        state1)
    assert state1.canvas_seeded is True
    # New turn — fresh stream state
    state2 = AGUIStreamState()
    assert state2.canvas_seeded is False


def test_replace_op_used_not_add():
    """Pre-condition (ii): ``replace`` not ``add`` for slot updates."""
    state = AGUIStreamState()
    state.canvas_seeded = True
    out = map_chat_stream_event(
        StateDeltaEvent(target="live", mode="delta", payload=_PAYLOAD),
        state)
    op = out[0]["delta"][0]
    assert op["op"] == "replace"
    assert op["op"] != "add"


# --- Invariant: STATE_DELTA never emitted before STATE_SNAPSHOT ------------


@given(
    target=st.sampled_from(["graph", "timeline", "findings", "live"]),
    mode=st.sampled_from(["snapshot", "delta"]),
)
@settings(max_examples=30, deadline=None)
def test_property_first_event_is_always_snapshot(target, mode):
    """For any first paint (any target, any explicit mode) the first emitted
    AG-UI event in a fresh turn MUST be STATE_SNAPSHOT — never STATE_DELTA."""
    state = AGUIStreamState()
    out = map_chat_stream_event(
        StateDeltaEvent(target=target, mode=mode, payload=_PAYLOAD), state)
    assert out[0]["type"] == AGUIEventType.STATE_SNAPSHOT
    assert out[0]["snapshot"] == {"canvas": {target: _PAYLOAD}}


def test_full_turn_sequence_snapshot_then_deltas():
    """End-to-end shape: SNAPSHOT first, then DELTA replace patches."""
    state = AGUIStreamState()
    s1 = StateDeltaEvent(target="graph", mode="snapshot", payload=_PAYLOAD)
    s2 = StateDeltaEvent(target="graph", mode="delta", payload=_PAYLOAD)
    s3 = StateDeltaEvent(target="findings", mode="delta", payload=_PAYLOAD)
    events = (
        map_chat_stream_event(s1, state)
        + map_chat_stream_event(s2, state)
        + map_chat_stream_event(s3, state)
    )
    types = [e["type"] for e in events]
    assert types[0] == AGUIEventType.STATE_SNAPSHOT
    assert all(t == AGUIEventType.STATE_DELTA for t in types[1:])


def test_done_after_state_delta_finalizes_cleanly():
    """A ``done`` event after canvas paints terminates the stream cleanly."""
    state = AGUIStreamState()
    map_chat_stream_event(
        StateDeltaEvent(target="graph", mode="snapshot", payload=_PAYLOAD),
        state)
    out = map_chat_stream_event(DoneEvent(reason="stop"), state)
    assert state.terminated is True
    # No tool/text messages opened — finalize emits nothing
    assert out == []


def test_terminated_state_drops_subsequent_events():
    """Once terminated, no more state events are emitted."""
    state = AGUIStreamState()
    map_chat_stream_event(DoneEvent(reason="stop"), state)
    out = map_chat_stream_event(
        StateDeltaEvent(target="graph", mode="snapshot", payload=_PAYLOAD),
        state)
    assert out == []
