"""Native-interrupt → AG-UI synthesis (bd:python-factory-6pagv).

CopilotKit v2 + ``@ag-ui/[email protected]`` have NO native interrupt event on
the wire (only ``@ag-ui/langgraph`` maps one, via forwardedProps — we are
not on langgraph). So we bridge two native primitives by SYNTHESIZING the
``fe_approve_shell`` tool-call lifecycle from a Strands ``InterruptEvent``:
``TOOL_CALL_START`` / ``TOOL_CALL_ARGS`` / ``TOOL_CALL_END`` with NO
``TOOL_CALL_RESULT`` — the exact END-only choreography the canvas
``_frontend_pending`` path uses (``ag_ui_mapper_chat_tool._on_tool_result``)
to make CopilotKit fire the FE handler and flip
``useHumanInTheLoop("fe_approve_shell")`` to ``executing`` (renders
``ShellApprovalCard`` unchanged).

The synthesized ``toolCallId`` is the Strands ``Interrupt.id`` so the FE
echoes it back; the chat adapter's interrupt-resume reads it as the
``interruptId`` (meta-architect ``3409d32a`` — wire the real id).

Split from ``ag_ui_mapper_chat`` to stay under the 200-LOC brick tenet.
"""
from __future__ import annotations

import json
import time
from typing import Any

from .ag_ui_mapper import AGUIEventType

_APPROVE_TOOL = "fe_approve_shell"


def _ts() -> float:
    return time.time()


def on_interrupt(event: Any, state: Any, close_reasoning: Any) -> list[dict]:
    """Synthesize the ``fe_approve_shell`` tool-call lifecycle (END-only).

    Args:
        event: The ``InterruptEvent`` (``interrupt_id``, ``tool``, ``command``).
        state: Per-turn ``AGUIStreamState`` — records the id in
            ``seen_tool_call_ids`` + ``result_emitted_tcids`` so the
            stream finalizer does not synthesize a spurious RESULT.
        close_reasoning: The mapper's ``_close_reasoning_if_open`` helper
            (passed in to avoid a circular import).
    """
    tcid = event.interrupt_id
    out: list[dict[str, Any]] = close_reasoning(state)
    state.seen_tool_call_ids.add(tcid)
    out.append({
        "type": AGUIEventType.TOOL_CALL_START,
        "toolCallId": tcid,
        "toolCallName": _APPROVE_TOOL,
        "timestamp": _ts(),
    })
    out.append({
        "type": AGUIEventType.TOOL_CALL_ARGS,
        "toolCallId": tcid,
        "delta": json.dumps({"tool": event.tool, "command": event.command}),
        "timestamp": _ts(),
    })
    # END only — no RESULT — so CopilotKit fires the FE handler (HITL card).
    out.append({
        "type": AGUIEventType.TOOL_CALL_END,
        "toolCallId": tcid,
        "timestamp": _ts(),
    })
    state.result_emitted_tcids.add(tcid)
    return out


__all__ = ["on_interrupt"]
