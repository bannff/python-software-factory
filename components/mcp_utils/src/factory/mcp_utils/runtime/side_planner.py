"""LLM-backed side-turn planner (feature-map row 19).

Turns a natural-language question into the ``[(tool_name, args), …]`` plan
:func:`side_turn.run_side_turn` executes. This is the ONE genuinely
model-coupled piece the earlier slices deliberately injected as ``plan`` —
built now as its own isolated, swappable unit.

Conservative by construction: the model is shown only the READ-ONLY
(``deterministic``) tools available (never operational/authoring — even if
the model hallucinated one, :mod:`side_tool_gate` would refuse it downstream,
but this keeps the prompt honest about what a side turn can do). Any
parse failure, non-JSON reply, or unresolvable tool name yields an EMPTY
plan (a turn that answers nothing) rather than guessing — a side turn must
never invent a tool call it cannot justify.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Callable

from .side_tool_policy import classify_side_tool

logger = logging.getLogger(__name__)

_PROMPT = (
    "You are answering a side question beside the main conversation, using "
    "ONLY the read-only tools listed below. Pick at most 3 tools whose "
    "result would help answer the question. If none apply, pick none.\n\n"
    "Available read-only tools:\n{tool_list}\n\n"
    "Question: {query}\n\n"
    "Reply with ONLY a JSON array of {{\"tool\": <name>, \"args\": {{}}}} "
    "objects (empty array if none apply). No prose, no markdown fences."
)
_MAX_TOOLS_SHOWN = 40
_MAX_PLAN_LENGTH = 3


def _read_only_tool_names(category_lookup: dict[str, str]) -> list[str]:
    names = sorted({
        name for name, category in category_lookup.items()
        if classify_side_tool(category).allowed and "_" in name  # skip dotted duplicates
    })
    return names[:_MAX_TOOLS_SHOWN]


def _parse_plan(raw: str, allowed: set[str]) -> list[tuple[str, dict[str, Any]]]:
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`").removeprefix("json").strip()
    try:
        parsed = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        logger.warning("[side_planner] non-JSON planner reply, empty plan")
        return []
    if not isinstance(parsed, list):
        return []
    plan: list[tuple[str, dict[str, Any]]] = []
    for entry in parsed[:_MAX_PLAN_LENGTH]:
        if not isinstance(entry, dict):
            continue
        name = entry.get("tool")
        args = entry.get("args", {})
        if isinstance(name, str) and name in allowed and isinstance(args, dict):
            plan.append((name, args))
    return plan


def build_llm_side_planner(
    complete: Callable[[str], str],
    category_lookup: Callable[[], dict[str, str]],
) -> Callable[[str], list[tuple[str, dict[str, Any]]]]:
    """Build a `plan(query)` callable for :func:`side_turn.run_side_turn`.

    ``complete`` is an injected ``str -> str`` completion (e.g.
    ``build_mcp_utils_complete(model_id)``); ``category_lookup`` is a
    zero-arg provider of the current ``tool_name -> category`` map (fresh
    per call, since bricks load lazily).
    """

    def plan(query: str) -> list[tuple[str, dict[str, Any]]]:
        allowed_names = _read_only_tool_names(category_lookup())
        if not allowed_names:
            return []
        prompt = _PROMPT.format(tool_list="\n".join(f"- {n}" for n in allowed_names), query=query)
        try:
            raw = complete(prompt)
        except Exception:
            logger.warning("[side_planner] completion call failed, empty plan", exc_info=True)
            return []
        return _parse_plan(raw, set(allowed_names))

    return plan


__all__ = ["build_llm_side_planner"]
