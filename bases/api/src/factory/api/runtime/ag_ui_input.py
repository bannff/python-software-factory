"""``RunAgentInput`` parsing helpers for the AG-UI SSE route.

bd-115z extends the body with two new fields:

- ``tools[]`` — CopilotKit ``useFrontendTool`` registrations,
  validated against ``factory.agent.interface.FrontendToolSpec``.
- ``context[]`` — bullets of canvas state, prepended to the user
  message as a labelled block so the LLM distinguishes FE-pushed
  context from the user prompt.

Lives in a sibling module so ``ag_ui_routes.py`` can stay a thin
transport shell under the 200 LOC budget.
"""
from __future__ import annotations

import json
from typing import Any


def parse_fe_tools(raw: Any) -> tuple[list[Any], str | None]:
    """Validate ``RunAgentInput.tools[]`` against ``FrontendToolSpec``.

    Returns ``(parsed, None)`` on success, ``([], error_message)`` on
    failure. ``FrontendToolSpec`` is imported lazily so the api base
    keeps a clean dependency graph (factory.agent.interface, no
    internal paths) and so tests that don't exercise the chat path
    don't pay the import cost.
    """
    if not raw:
        return [], None
    if not isinstance(raw, list):
        return [], "tools must be a list"
    try:
        from factory.agent.interface import FrontendToolSpec
        from pydantic import ValidationError
    except Exception:  # noqa: BLE001 — agent brick optional
        return [], None
    parsed: list[Any] = []
    for i, entry in enumerate(raw):
        if not isinstance(entry, dict):
            return [], f"tools[{i}] must be an object"
        try:
            parsed.append(FrontendToolSpec(**entry))
        except ValidationError as exc:
            return [], f"tools[{i}] invalid: {exc.errors()[0]['msg']}"
    return parsed, None


def parse_agent_id(forwarded_props: Any) -> str | None:
    """Extract the opaque persona selector from ``forwardedProps``.

    bd:python-factory-d4roe.3 — the FE puts the chat persona id at
    ``RunAgentInput.forwardedProps.companion_x_agent_id`` (via
    CopilotKit ``core.setProperties``). This helper pulls out the raw
    string and nothing else: the api base is a transport shell, so it
    does NOT resolve the persona, validate it against the registry, or
    branch on its value (meta-architect verdict ``a19ef414`` Q2). The
    opaque string threads straight down to ``_get_or_create`` where
    resolution lives. Returns ``None`` when absent or not a non-empty
    string → the chat adapter falls back to the env default, keeping
    forwardedProps-absent runs byte-identical to pre-Phase-2 behavior.
    """
    if not isinstance(forwarded_props, dict):
        return None
    value = forwarded_props.get("companion_x_agent_id")
    if isinstance(value, str) and value:
        return value
    return None


def parse_model_id(forwarded_props: Any) -> str | None:
    """Extract an opaque next-session model hint; resolution stays in Agent."""
    if not isinstance(forwarded_props, dict):
        return None
    value = forwarded_props.get("companion_x_model")
    if isinstance(value, str) and value:
        return value
    return None


def prefix_context(context_items: Any, user_msg: str) -> str:
    """Prepend ``RunAgentInput.context[]`` items to the user message.

    Each entry is a ``{description, value}`` object. Rendered as a
    single labelled block so the agent distinguishes FE-pushed canvas
    context from the user prompt. Non-dict entries are skipped silently.
    """
    if not isinstance(context_items, list) or not context_items:
        return user_msg
    blocks: list[str] = []
    for item in context_items:
        if not isinstance(item, dict):
            continue
        desc = str(item.get("description", "context"))
        val = item.get("value", "")
        if not isinstance(val, str):
            try:
                val = json.dumps(val, default=str)
            except Exception:  # noqa: BLE001
                val = str(val)
        blocks.append(f"- {desc}: {val}")
    if not blocks:
        return user_msg
    prefix = "Canvas context (system-supplied, FE-pushed):\n" + "\n".join(blocks)
    return f"{prefix}\n\n{user_msg}" if user_msg else prefix


__all__ = [
    "parse_agent_id", "parse_fe_tools", "parse_model_id", "prefix_context",
]
