"""Pydantic contracts for the agent brick's runtime ports.

Currently exposes ``ChatStreamEvent`` — the strict discriminated union
returned by ``ChatAgentPort.stream()``. Future Bedrock-direct or
Anthropic-native chat adapters implement the same Protocol and produce
events of these exact shapes, so the polymorphic boundary cannot leak
SDK-specific data.

Also exposes ``FrontendToolSpec`` (bd-115z), the contract for FE-side tools registered through CopilotKit v2. Forwarded through the AG-UI request body and compiled into LangChain tools for each scope-bound graph.

The mapping from LangChain/LangGraph message chunks, tool messages, reasoning events, and interrupts to this union lives in ``runtime/adapters/langchain_stream.py`` and ``langchain_chat.py``. AG-UI translation lives in the UI brick (``components/ui/runtime/ag_ui_mapper.py``).
"""
from __future__ import annotations

from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, ConfigDict, Field

# Discriminated-union variants. Each carries a `type` Literal so a
# downstream consumer (the AG-UI mapper, the Bedrock-Direct adapter
# tests, future replay tooling) can route on it without isinstance().


class _StrictModel(BaseModel):
    """Base — forbids extra fields so SDK shapes can't sneak through."""

    model_config = ConfigDict(extra="forbid")


class TextDeltaEvent(_StrictModel):
    """Token chunk for an in-flight assistant message."""

    type: Literal["text_delta"] = "text_delta"
    content: str
    message_id: str


class ToolCallDeltaEvent(_StrictModel):
    """Incremental tool-call signal.

    Carries ``tool_call_id`` plus an optional ``tool_name`` from LangChain message chunks. Mapper dedup is keyed off ``tool_call_id``: the first emission triggers ``TOOL_CALL_START`` and later chunks trigger ``TOOL_CALL_ARGS``. ``args_delta`` carries partial JSON arguments.
    """

    type: Literal["tool_call_delta"] = "tool_call_delta"
    tool_call_id: str
    tool_name: str | None = None
    # bd:python-factory-rk4hc (Contract A) — operational MODALITY axis,
    # orthogonal to _mcp_category; ui mapper stamps it as camelCase opKind.
    op_kind: Literal["shell", "read", "write", "authoring"] | None = None
    args_delta: str = ""
    parent_tool_call_id: str | None = None  # bd:python-factory-wipnv — spawn's outer toolUseId


class ToolResultEvent(_StrictModel):
    """Final result of a tool invocation.

    Produced from LangChain tool messages and normalized tool lifecycle events after one scoped MCP invocation completes.
    """

    type: Literal["tool_result"] = "tool_result"
    tool_call_id: str
    payload: Any = None
    is_error: bool = False


class ReasoningTextEvent(_StrictModel):
    """Extended-thinking chunk. UI may drop these in v1."""

    type: Literal["reasoning_text"] = "reasoning_text"
    content: str


class StepStartEvent(_StrictModel):
    """Entered a logical sub-step (e.g. ``"reasoning"``)."""

    type: Literal["step_start"] = "step_start"
    step_name: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class StepFinishEvent(_StrictModel):
    """Exited a logical sub-step."""

    type: Literal["step_finish"] = "step_finish"
    step_name: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class InterruptEvent(_StrictModel):
    """Legacy-compatible HITL interrupt event contract.

    Retained for transport readers and stored-event compatibility. The active LangChain/LangGraph chat path uses its scoped frontend interruption/state rails and does not currently emit this variant directly.
    """

    type: Literal["interrupt"] = "interrupt"
    interrupt_id: str
    tool: str
    command: str


class DoneEvent(_StrictModel):
    """Terminal — the run finished cleanly."""

    type: Literal["done"] = "done"
    reason: Literal["stop", "tool_use", "max_tokens", "error"] = "stop"


class ErrorEvent(_StrictModel):
    """Terminal — the run aborted with an error."""

    type: Literal["error"] = "error"
    message: str


class StateDeltaEvent(_StrictModel):
    """Carrier #2 wire signal — STATE_DELTA / STATE_SNAPSHOT (bd-D).

    Emitted by the current LangChain frontend-tool/state path when a ``ui_paint_canvas`` result carries the ``_a2ui_canvas`` sentinel. ``langchain_stream.pending_frontend_events`` translates persisted state to AG-UI ``STATE_SNAPSHOT`` or ``STATE_DELTA`` with an RFC 6902 replacement on ``/canvas/<target>``.

    See ``.agents/steering/a2ui-protocol.md`` (memory id
    ``86e40334-51a1-4d53-9105-76b2a3c564b3``) for the canonical
    four-carrier model.
    """

    type: Literal["state_delta"] = "state_delta"
    target: Literal["graph", "timeline", "findings", "live"]
    mode: Literal["snapshot", "delta"] = "snapshot"
    payload: dict[str, Any]


ChatStreamEvent = Annotated[
    Union[
        TextDeltaEvent,
        ToolCallDeltaEvent,
        ToolResultEvent,
        ReasoningTextEvent,
        StepStartEvent,
        StepFinishEvent,
        StateDeltaEvent,
        InterruptEvent,
        DoneEvent,
        ErrorEvent,
    ],
    Field(discriminator="type"),
]


class FrontendToolSpec(_StrictModel):
    """Contract for a CopilotKit ``useFrontendTool`` registration (bd-115z).

    The FE-side handler interprets ``parameters``, so on the Python side the schema is opaque. The active adapter compiles this minimal declaration into a scoped LangChain frontend tool that the model can request through CopilotKit v2.
    """

    name: str
    description: str
    parameters: dict[str, Any] = Field(default_factory=dict)


__all__ = [
    "ChatStreamEvent",
    "TextDeltaEvent",
    "ToolCallDeltaEvent",
    "ToolResultEvent",
    "ReasoningTextEvent",
    "StepStartEvent",
    "StepFinishEvent",
    "StateDeltaEvent",
    "InterruptEvent",
    "DoneEvent",
    "ErrorEvent",
    "FrontendToolSpec",
]
