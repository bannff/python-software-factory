"""Side-chat service facade (feature-map row 19).

The composition root that the `side/{open,turn,close}` endpoints expose: it
holds the per-slot conversation store and runs a side turn through the
read-only enforcement gate, wiring together every side primitive
(:mod:`side_conversation`, :mod:`side_turn`, :mod:`side_tool_gate`,
:mod:`side_tool_policy`).

The three model/transport-coupled dependencies are INJECTED, so the facade
itself is pure orchestration and fully unit-testable:

* ``planner``          — natural-language question → ``[(tool, args), …]`` (the
  deferred LLM step; a gateway wiring supplies the real chat-graph planner).
* ``category_lookup``  — a zero-arg provider returning the current
  ``tool_name → _mcp_category`` map (resolved per turn, since bricks load
  lazily); the gateway passes
  ``mcp_server.runtime.category_lookup.build_category_lookup``.
* ``dispatch``         — invoke a (read-only) tool; the gateway passes the
  aggregator call.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from .side_conversation import SideConversationStore, SideTurn
from .side_turn import SidePlanner, SideTurnResult, run_side_turn


@dataclass(frozen=True)
class SideOpenResult:
    slot: str
    turns: list[SideTurn]


class SideChatService:
    def __init__(
        self,
        *,
        planner: SidePlanner,
        category_lookup: Callable[[], dict[str, str]],
        dispatch: Callable[[str, dict[str, Any]], Any],
    ) -> None:
        self._store = SideConversationStore()
        self._planner = planner
        self._category_lookup = category_lookup
        self._dispatch = dispatch

    def open(self, slot: str) -> SideOpenResult:
        """Open (or return) the slot's side conversation."""
        conversation = self._store.open(slot)
        return SideOpenResult(slot=slot, turns=list(conversation.turns))

    def turn(self, slot: str, query: str) -> SideTurnResult:
        """Run one side turn — read-only lookups auto-run, changes refused."""
        return run_side_turn(
            self._store, slot, query,
            plan=self._planner,
            category_lookup=self._category_lookup(),
            dispatch=self._dispatch,
        )

    def close(self, slot: str) -> bool:
        """Discard the slot's side conversation. Returns whether one existed."""
        return self._store.close(slot)

    def is_open(self, slot: str) -> bool:
        return self._store.is_open(slot)


__all__ = ["SideChatService", "SideOpenResult"]
