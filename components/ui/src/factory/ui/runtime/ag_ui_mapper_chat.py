"""Chat stream → AG-UI translation.

Pure-function mapper from ``ChatStreamEvent`` to AG-UI protocol events.
``done``/``error`` synth ``TOOL_CALL_END``+``TOOL_CALL_RESULT`` for tcids
not closed via ``tool_result`` (bd-lmne, bd-3uhr). Reasoning emits
canonical ``REASONING_MESSAGE_*`` (bd-eyuj). FE tools (bd-ioyz) emit
``TOOL_CALL_END`` only — see ``_on_tool_result``. Assistant text emits a
per-message ``uuid4`` ``messageId`` (issue #106) with the upstream
``message_id`` used only as a change-detector — the AG-UI client keys
messages by ``messageId`` alone, so a constant upstream id would append
every turn's answer to the first turn's bubble.

Tool-call handler split to ``ag_ui_mapper_chat_tool`` (bd:python-factory-wipnv)
to stay under the 200-LOC tenet. ``spawn_parent_tcids`` added to state so
``_synth_unclosed_tool_ends`` can attach ``parentMessageId`` on synthesized
END+RESULT for unclosed sub-agent tool calls.
"""
from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from factory.agent.runtime.models import ChatStreamEvent

from .ag_ui_mapper import AGUIEventType
from .ag_ui_mapper_chat_interrupt import on_interrupt as _on_interrupt
from .ag_ui_mapper_chat_state import on_state_delta as _on_state_delta
from .ag_ui_mapper_chat_tool import (
    _emit_end_result,
    _on_tool_call_delta,
    _on_tool_result,
)


@dataclass
class AGUIStreamState:
    """Per-request mutable state for ``map_chat_stream_event``."""

    current_message_id: str | None = None
    # bd #106 — upstream id of the open message; the upstream id is only a
    # change-detector, never the emitted AG-UI ``messageId`` (which must be
    # unique per message so the client opens a new bubble each turn).
    current_upstream_id: str | None = None
    seen_tool_call_ids: set[str] = field(default_factory=set)
    result_emitted_tcids: set[str] = field(default_factory=set)
    # Upstream ids whose message has been closed (late deltas are dropped).
    ended_message_ids: set[str] = field(default_factory=set)
    reasoning_message_id: str | None = None
    terminated: bool = False
    canvas_seeded: bool = False
    # bd:python-factory-wipnv — maps sub_agent_tcid → spawn_tcid so
    # _synth_unclosed_tool_ends can attach parentMessageId on synthesized events.
    spawn_parent_tcids: dict[str, str] = field(default_factory=dict)


def map_chat_stream_event(
    event: ChatStreamEvent, state: AGUIStreamState,
) -> list[dict[str, Any]]:
    """Translate a single ``ChatStreamEvent``. Mutates ``state``."""
    if state.terminated:
        return []
    handler = _DISPATCH.get(event.type)
    return handler(event, state) if handler else []


def _ts() -> float:
    return time.time()


def _on_text_delta(event: Any, state: AGUIStreamState) -> list[dict]:
    upstream_id = event.message_id
    if upstream_id in state.ended_message_ids:
        return []  # closed message — drop
    out: list[dict[str, Any]] = _close_reasoning_if_open(state)
    if state.current_upstream_id != upstream_id:
        out.extend(_close_open_message(state))
        msg_id = str(uuid.uuid4())
        state.current_message_id = msg_id
        state.current_upstream_id = upstream_id
        out.append({"type": AGUIEventType.TEXT_MESSAGE_START,
                    "messageId": msg_id, "role": "assistant",
                    "timestamp": _ts()})
    out.append({"type": AGUIEventType.TEXT_MESSAGE_CONTENT,
                "messageId": state.current_message_id,
                "delta": event.content, "timestamp": _ts()})
    return out

def _on_tool_call_delta_wrapper(event: Any, state: AGUIStreamState) -> list[dict]:
    return _on_tool_call_delta(event, state, _close_reasoning_if_open)


def _on_tool_result_wrapper(event: Any, state: AGUIStreamState) -> list[dict]:
    return _on_tool_result(event, state, _close_reasoning_if_open)


def _on_reasoning_text(event: Any, state: AGUIStreamState) -> list[dict]:
    out: list[dict[str, Any]] = []
    if state.reasoning_message_id is None:
        msg_id = str(uuid.uuid4())
        state.reasoning_message_id = msg_id
        out.append({"type": AGUIEventType.REASONING_MESSAGE_START,
                    "messageId": msg_id, "role": "reasoning",
                    "timestamp": _ts()})
    out.append({"type": AGUIEventType.REASONING_MESSAGE_CONTENT,
                "messageId": state.reasoning_message_id,
                "delta": event.content, "timestamp": _ts()})
    return out


def _close_reasoning_if_open(state: AGUIStreamState) -> list[dict[str, Any]]:
    if state.reasoning_message_id is None:
        return []
    out = [{"type": AGUIEventType.REASONING_MESSAGE_END,
            "messageId": state.reasoning_message_id, "timestamp": _ts()}]
    state.reasoning_message_id = None
    return out


def _on_step_start(event: Any, state: AGUIStreamState) -> list[dict]:
    return [{"type": AGUIEventType.STEP_STARTED,
             "stepName": event.step_name, "timestamp": _ts()}]


def _on_step_finish(event: Any, state: AGUIStreamState) -> list[dict]:
    return [{"type": AGUIEventType.STEP_FINISHED,
             "stepName": event.step_name, "timestamp": _ts()}]


def _synth_unclosed_tool_ends(state: AGUIStreamState) -> list[dict]:
    pending = state.seen_tool_call_ids - state.result_emitted_tcids
    if not pending:
        return []
    content = json.dumps(
        {"status": "incomplete", "reason": "stream_finalized"})
    state.result_emitted_tcids.update(pending)
    out: list[dict[str, Any]] = []
    for tcid in pending:
        events = _emit_end_result(tcid, content)
        # bd:python-factory-wipnv — attach parentMessageId for sub-agent calls
        if tcid in state.spawn_parent_tcids:
            parent = state.spawn_parent_tcids[tcid]
            for evt in events:
                evt["parentMessageId"] = parent
        out.extend(events)
    return out


def _close_open_message(state: AGUIStreamState) -> list[dict[str, Any]]:
    if state.current_message_id is None:
        return []
    out = [{"type": AGUIEventType.TEXT_MESSAGE_END,
            "messageId": state.current_message_id, "timestamp": _ts()}]
    if state.current_upstream_id is not None:
        state.ended_message_ids.add(state.current_upstream_id)
    state.current_message_id = None
    state.current_upstream_id = None
    return out


def _finalize(state: AGUIStreamState) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = _synth_unclosed_tool_ends(state)
    out.extend(_close_reasoning_if_open(state))
    out.extend(_close_open_message(state))
    state.terminated = True
    return out


def _on_done(event: Any, state: AGUIStreamState) -> list[dict]:
    return _finalize(state)


def _on_error(event: Any, state: AGUIStreamState) -> list[dict]:
    out = _finalize(state)
    out.append({"type": AGUIEventType.RUN_ERROR,
                "message": event.message, "timestamp": _ts()})
    return out

_DISPATCH = {
    "text_delta": _on_text_delta,
    "tool_call_delta": _on_tool_call_delta_wrapper,
    "tool_result": _on_tool_result_wrapper,
    "reasoning_text": _on_reasoning_text,
    "step_start": _on_step_start,
    "step_finish": _on_step_finish,
    "state_delta": lambda e, s: _on_state_delta(e, s, _close_reasoning_if_open),
    "interrupt": lambda e, s: _on_interrupt(e, s, _close_reasoning_if_open),
    "done": _on_done, "error": _on_error,
}


__all__ = ["map_chat_stream_event", "AGUIStreamState"]