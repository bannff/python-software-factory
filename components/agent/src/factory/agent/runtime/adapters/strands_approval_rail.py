"""Owner-scoped tool-approval rail for the Strands chat adapter.

``HookProvider`` on ``BeforeToolCallEvent``: policy-listed tools pause the
event loop with the EXACT ``_approval_pending`` payload shape the LangChain
adapter emits (``langchain_tools._approval_decision``), so the FE approval
card and AG-UI interrupt rail stay byte-identical across runtimes.

Same policy store as ``langchain_tools`` — an unlisted tool or a
missing tenant/owner identity preserves autonomy (no interrupt).

Resume contract (strands 1.56, live-verified): the paused loop surfaces
``stop_reason='interrupt'`` with ``AgentResult.interrupts``; re-invoking
the SAME cached agent with
``[{"interruptResponse": {"interruptId", "response"}}]`` replays the
pending toolUse WITHOUT a fresh model call — the second
``event.interrupt()`` call inside this hook returns the stored response.
``approved is True`` → the tool proceeds (hook returns normally);
anything else → ``event.cancel_tool`` surfaces an error ``ToolResult``
and the loop completes.
"""
from __future__ import annotations

import json
from typing import Any

from strands.hooks import BeforeToolCallEvent, HookProvider, HookRegistry

from ..approval_policy import ApprovalPolicyStore

_INTERRUPT_NAME = "tool_approval"
_MAX_COMMAND = 300


class StrandsApprovalRail(HookProvider):
    """Pause listed tool calls on ``BeforeToolCallEvent`` for approval."""

    def __init__(self, store: ApprovalPolicyStore | None) -> None:
        self._store = store

    def register_hooks(self, registry: HookRegistry, **kwargs: Any) -> None:
        registry.add_callback(BeforeToolCallEvent, self._before_tool_call)

    def _before_tool_call(self, event: BeforeToolCallEvent) -> None:
        from .strands_agent_factory import _CURRENT_INVOCATION

        request = _CURRENT_INVOCATION.get()
        name = str(event.tool_use.get("name", ""))
        if (
            self._store is None or request is None
            or request.tenant_id is None or request.owner_id is None
            or name not in self._store.get(request.tenant_id, request.owner_id).tool_names
        ):
            return
        reply = event.interrupt(_INTERRUPT_NAME, reason=_pending_payload(event.tool_use))
        if not (isinstance(reply, dict) and reply.get("approved") is True):
            event.cancel_tool = "tool approval was not granted"


def _pending_payload(tool_use: dict[str, Any]) -> dict[str, Any]:
    """The ``_approval_pending`` payload — byte-identical contract."""
    tool_call_id = str(tool_use.get("toolUseId", ""))
    preview = json.dumps(tool_use.get("input", {}), sort_keys=True, default=str)
    return {
        "_approval_pending": True,
        "interrupt_id": tool_call_id,
        "tool_call_id": tool_call_id,
        "tool": str(tool_use.get("name", "")),
        "command": preview[:_MAX_COMMAND],
    }


__all__ = ["StrandsApprovalRail"]
