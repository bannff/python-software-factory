"""Interrupt-resume prompt builders for the Strands chat facade.

The FE re-POSTs the full ``RunAgentInput.messages`` array on resume
turns; these helpers map its trailing ``role:"tool"`` entries onto the
cached agent's pending interrupts (the same extraction
``langchain_stream._tool_replies`` performs for the LangChain adapter).
"""
from __future__ import annotations

import json
from typing import Any


def resume_responses(agent: Any, messages: list[dict[str, Any]] | None) -> list[dict[str, Any]] | None:
    """Build the strands ``interruptResponse`` resume prompt.

    Re-POSTed FE messages carry trailing ``role:"tool"`` entries; when the
    cached agent sits in an interrupt state, map each pending interrupt's
    ``tool_call_id`` (the approval payload echoes the toolUseId) onto the
    FE tool reply. ``None`` when this is not an approval-resume turn —
    ordinary turns stream the plain prompt unchanged.
    """
    if not messages or not agent._interrupt_state.activated:
        return None
    replies = _tool_replies(messages)
    responses: list[dict[str, Any]] = []
    for interrupt in agent._interrupt_state.interrupts.values():
        if interrupt.response is not None:
            continue
        reason = interrupt.reason if isinstance(interrupt.reason, dict) else {}
        tool_call_id = str(reason.get("tool_call_id") or "")
        if tool_call_id not in replies:
            return None
        responses.append({
            "interruptResponse": {"interruptId": interrupt.id, "response": replies[tool_call_id]},
        })
    return responses or None


def _tool_replies(messages: list[dict[str, Any]]) -> dict[str, Any]:
    """Extract tool replies from trailing ``role:"tool"`` entries.

    Same extraction as ``langchain_stream._tool_replies``: JSON-encoded
    content blocks are unwrapped once.
    """
    replies: dict[str, Any] = {}
    for message in messages or ():
        if not isinstance(message, dict) or message.get("role") != "tool":
            continue
        tool_call_id = message.get("toolCallId") or message.get("tool_call_id")
        if not tool_call_id:
            continue
        content = message.get("content")
        if isinstance(content, str):
            try:
                content = json.loads(content)
            except (TypeError, ValueError):
                pass
        replies[str(tool_call_id)] = content
    return replies


__all__ = ["resume_responses"]
