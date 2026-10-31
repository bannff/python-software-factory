"""Side-turn executor: orchestrates one scratch side turn (feature-map row 19).

Composes the three side primitives — the conversation lifecycle
(:mod:`side_conversation`), the read-only enforcement gate
(:mod:`side_tool_gate`), and (transitively) the policy — into one side turn:
open the slot's side conversation, record the user's question, run any tools
the turn wants through the gate (read-only dispatched, changes refused), and
record each outcome.

The one genuinely model-coupled piece — turning the natural-language question
into a list of tool calls — is injected as ``plan`` (the deferred LLM step),
so this orchestration is pure and fully unit-testable. When ``plan`` is later
backed by the chat graph, and this is bound to the ``side/turn`` endpoint, the
side turn runs for real with the SAME structural no-change guarantee.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from .side_conversation import SideConversationStore, SideTurn
from .side_tool_gate import run_side_tool

#: (query) -> ordered [(tool_name, args), ...] the side turn wants to run.
SidePlanner = Callable[[str], list[tuple[str, dict[str, Any]]]]


@dataclass(frozen=True)
class SideTurnResult:
    """What one side turn produced."""

    turns: list[SideTurn]     # turns appended this call (user + per-tool)
    refused: list[str]        # names of tools refused as non-read-only


def run_side_turn(
    store: SideConversationStore,
    slot: str,
    query: str,
    *,
    plan: SidePlanner,
    category_lookup: dict[str, str],
    dispatch: Callable[[str, dict[str, Any]], Any],
) -> SideTurnResult:
    """Run one side turn for ``slot``, recording every step in the store."""
    store.open(slot)
    appended: list[SideTurn] = [store.append(slot, "user", query)]
    refused: list[str] = []
    for tool_name, args in plan(query):
        outcome = run_side_tool(
            tool_name, args, category_lookup=category_lookup, dispatch=dispatch,
        )
        if outcome.ok:
            appended.append(store.append(slot, "tool", f"{tool_name} → {outcome.result!r}"))
        else:
            refused.append(tool_name)
            appended.append(store.append(slot, "tool", f"{tool_name} refused: {outcome.refusal}"))
    return SideTurnResult(turns=appended, refused=refused)


__all__ = ["SidePlanner", "SideTurnResult", "run_side_turn"]
