"""Per-slot side-chat conversation lifecycle (feature-map row 19).

The scratch-conversation state the side endpoints drive
(``POST /api/chat/slots/{slot}/side/{open,turn,close}``): one ephemeral side
conversation per chat slot, holding an ordered turn transcript. Deliberately
in-memory and process-local — a side chat is throwaway scratch beside the main
turn, not durable session state, so it is intentionally NOT persisted.

Pure state management: ``open`` starts (or returns) a slot's side
conversation, ``append`` records a turn (only while open), ``close`` discards
it. The turn *executor* (LLM → tool selection through
:mod:`side_tool_gate`) is a separate, deferred piece that will append its
turns here.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class SideTurn:
    """One line of a side conversation."""

    role: str  # "user" | "assistant" | "tool"
    text: str


@dataclass
class SideConversation:
    """A slot's ephemeral side conversation."""

    slot: str
    turns: list[SideTurn] = field(default_factory=list)


class SideConversationStore:
    """In-memory registry of open side conversations, keyed by chat slot."""

    def __init__(self) -> None:
        self._conversations: dict[str, SideConversation] = {}

    def is_open(self, slot: str) -> bool:
        return slot in self._conversations

    def open(self, slot: str) -> SideConversation:
        """Start a side conversation for ``slot``, or return the open one.

        Idempotent: reopening an already-open slot returns the existing
        conversation rather than wiping its scratch transcript.
        """
        conversation = self._conversations.get(slot)
        if conversation is None:
            conversation = SideConversation(slot=slot)
            self._conversations[slot] = conversation
        return conversation

    def append(self, slot: str, role: str, text: str) -> SideTurn:
        """Record a turn. Raises ``KeyError`` if the slot has no open side."""
        conversation = self._conversations.get(slot)
        if conversation is None:
            raise KeyError(f"no open side conversation for slot {slot!r}")
        turn = SideTurn(role=role, text=text)
        conversation.turns.append(turn)
        return turn

    def get(self, slot: str) -> SideConversation | None:
        return self._conversations.get(slot)

    def close(self, slot: str) -> bool:
        """Discard a slot's side conversation. Returns whether one existed."""
        return self._conversations.pop(slot, None) is not None


__all__ = ["SideTurn", "SideConversation", "SideConversationStore"]
