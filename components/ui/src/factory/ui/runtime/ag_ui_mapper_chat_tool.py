"""Tool-call handlers extracted from ``ag_ui_mapper_chat`` (bd:python-factory-wipnv).

Extracted to keep ``ag_ui_mapper_chat`` under the 200-LOC brick tenet.
Pattern mirrors ``ag_ui_mapper_chat_state`` (same module-split approach):
``close_reasoning`` helper is passed in to avoid a circular import with
the parent mapper module.

Key change (bd:python-factory-wipnv): ``_on_tool_call_delta`` now reads
``parent_tool_call_id`` from the event and, when present, sets
``parentMessageId`` on the ``TOOL_CALL_START`` event so ``@ag-ui/client``
``applyEvents`` places the sub-agent tool call inside the spawn card's
``AssistantMessage.toolCalls[]`` rather than creating an orphan message.

Also records the mapping in ``state.spawn_parent_tcids`` so that
``_synth_unclosed_tool_ends`` in the parent module can attach
``parentMessageId`` to synthesized END+RESULT events for any unclosed
sub-agent tool call at stream termination.
"""
from __future__ import annotations

import json
import time
import uuid
from typing import Any

from .ag_ui_mapper import AGUIEventType


def _ts() -> float:
    return time.time()


def _emit_end_result(tcid: str, content: str) -> list[dict[str, Any]]:
    return [
        {"type": AGUIEventType.TOOL_CALL_END,
         "toolCallId": tcid, "timestamp": _ts()},
        {"type": AGUIEventType.TOOL_CALL_RESULT,
         "messageId": str(uuid.uuid4()), "toolCallId": tcid,
         "content": content, "role": "tool", "timestamp": _ts()},
    ]


def _on_tool_call_delta(event: Any, state: Any, close_reasoning: Any) -> list[dict]:
    """Emit TOOL_CALL_START / TOOL_CALL_ARGS for a ToolCallDeltaEvent.

    Args:
        event: The ToolCallDeltaEvent instance.
        state: Per-turn AGUIStreamState — mutates seen_tool_call_ids +
            spawn_parent_tcids.
        close_reasoning: Reference to the mapper's
            _close_reasoning_if_open helper. Passed in to avoid a
            circular import cycle with the mapper module.

    When ``event.parent_tool_call_id`` is set, stamps ``parentMessageId``
    on the START event so the AG-UI client nests this call inside the
    spawn card (bd:python-factory-wipnv). When ``event.op_kind`` is set,
    stamps camelCase ``opKind`` on the START event for the IDE terminal
    mirror (bd:python-factory-rk4hc, Contract A).
    """
    tcid = event.tool_call_id
    out: list[dict[str, Any]] = close_reasoning(state)
    if tcid not in state.seen_tool_call_ids:
        state.seen_tool_call_ids.add(tcid)
        evt: dict[str, Any] = {
            "type": AGUIEventType.TOOL_CALL_START,
            "toolCallId": tcid,
            "toolCallName": event.tool_name or "unknown",
            "timestamp": _ts(),
        }
        # bd:python-factory-wipnv — nest sub-agent tool calls inside spawn card
        parent = getattr(event, "parent_tool_call_id", None)
        if parent:
            evt["parentMessageId"] = parent
            state.spawn_parent_tcids[tcid] = parent
        # bd:python-factory-rk4hc (Contract A) — stamp camelCase opKind for the
        # IDE terminal mirror, mirroring how parentMessageId is conditionally
        # added. Final shape: {type,toolCallId,toolCallName,timestamp,
        # parentMessageId?,opKind?}.
        op = getattr(event, "op_kind", None)
        if op:
            evt["opKind"] = op
        out.append(evt)
    if event.args_delta:
        out.append({
            "type": AGUIEventType.TOOL_CALL_ARGS,
            "toolCallId": tcid,
            "delta": event.args_delta,
            "timestamp": _ts(),
        })
    return out


def _on_tool_result(event: Any, state: Any, close_reasoning: Any) -> list[dict]:
    """Emit TOOL_CALL_END + TOOL_CALL_RESULT for a ToolResultEvent.

    Args:
        event: The ToolResultEvent instance.
        state: Per-turn AGUIStreamState.
        close_reasoning: Reference to the mapper's
            _close_reasoning_if_open helper. Passed in to avoid a
            circular import cycle with the mapper module.
    """
    # Drop tool_result without a prior tool_call_delta (cancelled-call race).
    if event.tool_call_id not in state.seen_tool_call_ids:
        return []
    out: list[dict[str, Any]] = close_reasoning(state)
    payload = event.payload
    # bd-ioyz FE-tool sentinel: emit END only (CopilotKit useFrontendTool fires FE handler).
    if isinstance(payload, dict) and payload.get("_frontend_pending"):
        state.result_emitted_tcids.add(event.tool_call_id)
        out.append({"type": AGUIEventType.TOOL_CALL_END,
                    "toolCallId": event.tool_call_id, "timestamp": _ts()})
        return out
    try:
        content = json.dumps(payload, default=str)
    except (TypeError, ValueError):
        content = json.dumps(str(payload))
    state.result_emitted_tcids.add(event.tool_call_id)
    out.extend(_emit_end_result(event.tool_call_id, content))
    return out


__all__ = ["_on_tool_call_delta", "_on_tool_result", "_emit_end_result"]
