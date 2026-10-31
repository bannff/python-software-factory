"""Read-only tool policy for the side-chat scratch turn (feature-map row 19).

A side turn (upstream ``handlers/side.py``) runs *read-only lookups without
asking; changes are refused*. That maps exactly onto the existing EFFECT axis
``_mcp_category`` (see ``mcp_server.runtime.category_lookup``): ``deterministic``
tools are reads, while ``operational`` / ``authoring`` are the verbs that
mutate ("verbs a human can fire"). So a side turn may auto-run ``deterministic``
tools without approval and MUST refuse the rest.

Tools with no category — e.g. the native ``shell`` / ``python_repl`` strands
tools, which carry no ``_mcp_category`` — are refused by default: a side turn
cannot statically prove an arbitrary shell command is read-only, and refusing
is the safe direction the row's contract demands (the row's "read-only shell"
nuance would need per-command inspection, a later refinement).

Pure classification only. The side-turn executor (deferred, needs the chat
graph) consumes these decisions to decide auto-run vs refusal.
"""

from __future__ import annotations

from dataclasses import dataclass

#: Categories a side turn may auto-run without approval (the read/effect-free axis).
READ_ONLY_CATEGORIES: frozenset[str] = frozenset({"deterministic"})


@dataclass(frozen=True)
class SideToolDecision:
    """Whether a side turn may auto-run a tool, plus a truthful reason."""

    allowed: bool
    reason: str


def classify_side_tool(category: str | None) -> SideToolDecision:
    """Decide whether a tool of ``category`` may run in a side turn.

    ``deterministic`` → allowed (a read). ``operational`` / ``authoring`` →
    refused (a change). ``None``/unknown → refused (cannot prove read-only).
    """
    if category in READ_ONLY_CATEGORIES:
        return SideToolDecision(True, f"read-only ({category})")
    if category is None:
        return SideToolDecision(False, "refused: uncategorised tool cannot be proven read-only")
    return SideToolDecision(False, f"refused: '{category}' tools make changes")


def is_side_read_only(category: str | None) -> bool:
    """Convenience boolean form of :func:`classify_side_tool`."""
    return classify_side_tool(category).allowed


def partition_side_tools(
    category_lookup: dict[str, str],
) -> tuple[list[str], list[str]]:
    """Split a ``tool_name -> category`` map into (allowed, refused) name lists.

    Names are returned sorted so callers (and tests) get a stable order.
    """
    allowed: list[str] = []
    refused: list[str] = []
    for name, category in category_lookup.items():
        (allowed if is_side_read_only(category) else refused).append(name)
    return sorted(allowed), sorted(refused)


__all__ = [
    "READ_ONLY_CATEGORIES",
    "SideToolDecision",
    "classify_side_tool",
    "is_side_read_only",
    "partition_side_tools",
]
