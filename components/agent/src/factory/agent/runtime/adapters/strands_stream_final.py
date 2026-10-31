"""Stream-event finalization for the Strands chat facade (phase 2).

Split from ``strands_chat.py`` (LOC tenet): the terminal-event
intercept that turns a strands interrupt pause into the LangChain
adapter's event order — ``InterruptEvent`` (approval card) then
``DoneEvent(reason='tool_use')`` — lives here with the FE-sentinel
unwrap it shares the dispatch loop with.
"""
from __future__ import annotations

from typing import Any

from ..models import InterruptEvent


def pending_approval_interrupts(agent: Any) -> list[InterruptEvent]:
    """Unanswered interrupts as approval-card events (None responses)."""
    return [
        _approval_event(interrupt)
        for interrupt in agent._interrupt_state.interrupts.values()
        if interrupt.response is None
        and isinstance(interrupt.reason, dict)
        and interrupt.reason.get("_approval_pending")
    ]


def _approval_event(interrupt: Any) -> InterruptEvent:
    approval = interrupt.reason
    return InterruptEvent(
        interrupt_id=str(approval.get("interrupt_id", "")),
        tool=str(approval.get("tool", "tool")),
        command=str(approval.get("command", "")),
    )


def finalize_done_payload(agent: Any, payload: dict[str, Any]) -> tuple[list[InterruptEvent], dict[str, Any]]:
    """Intercept a clean-stop done: an approval pause surfaces the card
    first and re-reasons the done as ``tool_use`` (langchain_chat order:
    interrupt event, then done). Non-pauses pass through untouched.
    """
    if payload.get("reason") != "stop":
        return [], payload
    pending = pending_approval_interrupts(agent)
    if not pending:
        return [], payload
    return pending, {"reason": "tool_use"}


__all__ = ["finalize_done_payload", "pending_approval_interrupts", "unwrap_frontend_sentinel"]


def unwrap_frontend_sentinel(payload: dict[str, Any]) -> dict[str, Any]:
    """Keep the ``_frontend_pending`` sentinel payload byte-identical:
    the AG-UI mapper routes the FE handler round-trip off these fields."""
    inner = payload.get("payload")
    if isinstance(inner, list) and len(inner) == 1:
        json_block = inner[0].get("json") if isinstance(inner[0], dict) else None
        if isinstance(json_block, dict) and json_block.get("_frontend_pending") is True:
            return {
                "tool_call_id": payload["tool_call_id"], "payload": json_block,
                "is_error": False,
            }
    return payload
