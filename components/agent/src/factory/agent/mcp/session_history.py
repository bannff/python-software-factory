"""Authorized Agent-owned chat history MCP surface."""
from __future__ import annotations

from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from factory.mcp_utils.interface import ToolResult, deterministic, fail, get_envelope, get_service, ok


class StrictDTO(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class SessionHistoryInput(StrictDTO):
    session_id: str = Field(min_length=1, max_length=128)


class HistoryFunction(StrictDTO):
    name: str
    arguments: str


class HistoryToolCall(StrictDTO):
    id: str
    type: Literal["function"] = "function"
    function: HistoryFunction


class HistoryMessage(StrictDTO):
    id: str
    role: Literal["user", "assistant", "system", "tool"]
    content: str
    tool_calls: list[HistoryToolCall] = Field(default_factory=list)
    tool_call_id: str | None = None


class SessionHistoryOutput(StrictDTO):
    session_id: str
    thread_id: str
    messages: list[HistoryMessage]


def register(mcp: Any) -> None:
    @mcp.tool()
    @deterministic(input_model=SessionHistoryInput, output_model=SessionHistoryOutput)
    async def session_history(session_id: str) -> ToolResult[SessionHistoryOutput]:
        try:
            session = _authorized_session(session_id)
            if session is None:
                return fail("session_not_found")
            from ..runtime.chat import get_chat_agent
            history = getattr(get_chat_agent(), "history", None)
            if history is None:
                return fail("history_unavailable")
            messages = await history(session["agent_id"], session["thread_id"])
            return ok(SessionHistoryOutput(
                session_id=session_id, thread_id=session["thread_id"],
                messages=[HistoryMessage.model_validate(item) for item in messages],
            ))
        except RuntimeError:
            return fail("history_unavailable")


def _authorized_session(session_id: str) -> dict[str, Any] | None:
    envelope = get_envelope()
    if not isinstance(envelope, dict) or not envelope.get("tenant_id") or not envelope.get("principal_id"):
        return None
    factory = get_service("tool_invoker_for_caller")
    invoker = factory("agent") if callable(factory) else None
    if not callable(invoker):
        raise RuntimeError("agent caller-bound tool invoker is unavailable")
    raw = invoker(
        {"brick_name": "session", "tool_name": "get"},
        arguments={"session_id": session_id, "envelope": envelope},
        idempotency_key=f"history:{session_id}:{uuid4().hex}", envelope=envelope,
    )
    structured = raw.get("result", {}).get("structured_content") if isinstance(raw, dict) else None
    if not isinstance(structured, dict):
        raise RuntimeError("session MCP transport failed")
    if structured.get("error") == "session_not_found":
        return None
    if structured.get("ok") is not True:
        raise RuntimeError("session history authorization failed")
    data = structured.get("data")
    return data.get("session") if structured.get("ok") is True and isinstance(data, dict) else None


__all__ = ["HistoryMessage", "SessionHistoryOutput", "register"]
