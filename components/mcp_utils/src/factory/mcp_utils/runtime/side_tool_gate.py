"""Read-only enforcement gate for side-chat tool calls (feature-map row 19).

The concrete "changes are refused" point of a side turn. Given a tool name,
this looks up the tool's EFFECT category (``_mcp_category`` via
:func:`mcp_server.runtime.category_lookup.build_category_lookup`) and applies
:mod:`side_tool_policy`: a ``deterministic`` (read) tool is dispatched
without approval; anything else — mutating (``operational``/``authoring``) or
uncategorised — is refused BEFORE dispatch, so a side turn can never make a
change.

``dispatch`` is injected (the caller supplies the real aggregator call), so
this stays pure and unit-testable and carries no MCP-boundary knowledge.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from .side_tool_policy import classify_side_tool


@dataclass(frozen=True)
class SideToolOutcome:
    """Result of a gated side-turn tool call."""

    ok: bool
    result: Any | None = None
    refusal: str | None = None


def _category_for(tool_name: str, category_lookup: dict[str, str]) -> str | None:
    # build_category_lookup keys both the dotted and underscore-normalised
    # forms; try the given name then its normalised sibling.
    return category_lookup.get(tool_name) or category_lookup.get(
        tool_name.replace(".", "_")
    )


def run_side_tool(
    tool_name: str,
    args: dict[str, Any],
    *,
    category_lookup: dict[str, str],
    dispatch: Callable[[str, dict[str, Any]], Any],
) -> SideToolOutcome:
    """Dispatch ``tool_name`` only if the read-only policy allows it.

    A refused call NEVER touches ``dispatch`` — the guarantee that a side turn
    makes no changes holds structurally, not by convention.
    """
    decision = classify_side_tool(_category_for(tool_name, category_lookup))
    if not decision.allowed:
        return SideToolOutcome(ok=False, refusal=decision.reason)
    return SideToolOutcome(ok=True, result=dispatch(tool_name, args))


__all__ = ["SideToolOutcome", "run_side_tool"]
