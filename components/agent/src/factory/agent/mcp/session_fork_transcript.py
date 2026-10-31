"""Authorized Agent-owned transcript fork (row 14, feature-map).

Completes the other half of session fork: ``session_fork`` (session
brick) creates the new session ROW with the source's exact bindings;
THIS tool copies the actual checkpoint transcript onto the new thread,
mirroring ``session_history.py``'s exact cross-brick-authorization shape
(read both session rows through the trusted ``tool_invoker_for_caller``
seam, then drive the chat adapter -- never a direct session-brick
import).
"""
from __future__ import annotations

from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from factory.mcp_utils.interface import ToolResult, fail, get_envelope, get_service, ok, operational


class StrictDTO(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class ForkTranscriptInput(StrictDTO):
    source_session_id: str = Field(min_length=1, max_length=128)
    target_session_id: str = Field(min_length=1, max_length=128)


class ForkTranscriptOutput(StrictDTO):
    copied: bool


def register(mcp: Any) -> None:
    @mcp.tool()
    @operational(input_model=ForkTranscriptInput, output_model=ForkTranscriptOutput,
                 idempotent=False)
    async def session_fork_transcript(
        source_session_id: str, target_session_id: str,
    ) -> ToolResult[ForkTranscriptOutput]:
        try:
            source = _authorized_session(source_session_id)
            target = _authorized_session(target_session_id)
            if source is None or target is None:
                return fail("session_not_found")
            if source["agent_id"] != target["agent_id"]:
                # A fork never changes persona (session_fork enforces this
                # too) -- refuse rather than silently copy across personas,
                # which would land the transcript under a checkpoint key
                # neither session's real chat adapter would ever read.
                return fail("session_agent_mismatch")
            from ..runtime.chat import get_chat_agent
            fork_thread = getattr(get_chat_agent(), "fork_thread", None)
            if fork_thread is None:
                return fail("history_unavailable")
            copied = await fork_thread(
                source["agent_id"], source["thread_id"], target["thread_id"],
            )
            return ok(ForkTranscriptOutput(copied=copied))
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
        idempotency_key=f"fork-transcript:{session_id}:{uuid4().hex}", envelope=envelope,
    )
    structured = raw.get("result", {}).get("structured_content") if isinstance(raw, dict) else None
    if not isinstance(structured, dict):
        raise RuntimeError("session MCP transport failed")
    if structured.get("error") == "session_not_found":
        return None
    if structured.get("ok") is not True:
        raise RuntimeError("session fork-transcript authorization failed")
    data = structured.get("data")
    return data.get("session") if structured.get("ok") is True and isinstance(data, dict) else None


__all__ = ["ForkTranscriptInput", "ForkTranscriptOutput", "register"]
