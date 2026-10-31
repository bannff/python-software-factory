"""Tests for the side-chat conversation lifecycle store (feature-map row 19)."""

from __future__ import annotations

import pytest

from factory.mcp_utils.runtime.side_conversation import SideConversationStore


def test_open_creates_and_is_idempotent():
    store = SideConversationStore()
    assert store.is_open("slot-1") is False
    convo = store.open("slot-1")
    assert store.is_open("slot-1") is True
    store.append("slot-1", "user", "hi")
    # Reopening must NOT wipe the existing scratch transcript.
    again = store.open("slot-1")
    assert again is convo
    assert [t.text for t in again.turns] == ["hi"]


def test_append_records_turns_in_order():
    store = SideConversationStore()
    store.open("s")
    store.append("s", "user", "what changed?")
    store.append("s", "assistant", "checking…")
    convo = store.get("s")
    assert [(t.role, t.text) for t in convo.turns] == [
        ("user", "what changed?"), ("assistant", "checking…"),
    ]


def test_append_without_open_raises():
    store = SideConversationStore()
    with pytest.raises(KeyError):
        store.append("ghost", "user", "x")


def test_close_discards_and_is_idempotent():
    store = SideConversationStore()
    store.open("s")
    assert store.close("s") is True
    assert store.is_open("s") is False
    assert store.get("s") is None
    assert store.close("s") is False  # already gone
