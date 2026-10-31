"""Authorized Agent-owned turn regenerate (row 16, feature-map).

"Re-run a turn, keep and switch between answers" — unlike rewind (row
15), regenerate creates a genuine NEW sibling checkpoint branch (the
ORIGINAL reply stays independently resumable, never overwritten) via
``LangChainChatAgent.regenerate_turn``, then persists the new branch as
the thread's "current" one via the SAME ``session_set_active_checkpoint``
primitive rewind uses. Mirrors ``session_rewind.py``'s exact
cross-brick-authorization shape (read the session through the trusted
``tool_invoker_for_caller`` seam, drive the chat adapter, persist the
result through a second cross-brick call — never a direct session-brick
import).
"""
from __future__ import annotations

from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from factory.mcp_utils.interface import ToolResult, fail, get_envelope, get_service, ok, operational


class StrictDTO(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class RegenerateSessionInput(StrictDTO):
    session_id: str = Field(min_length=1, max_length=128)
    message_id: str = Field(min_length=1, max_length=128)
    new_prompt: str = Field(min_length=1, max_length=32_768)
    expected_revision: int = Field(ge=1)


class RegenerateSessionOutput(StrictDTO):
    checkpoint_id: str | None = None
    regenerated: bool


def register(mcp: Any) -> None:
    @mcp.tool()
    @operational(input_model=RegenerateSessionInput, output_model=RegenerateSessionOutput,
                 idempotent=False)
    async def session_regenerate(
        session_id: str, message_id: str, new_prompt: str, expected_revision: int,
    ) -> ToolResult[RegenerateSessionOutput]:
        try:
            session = _authorized_session(session_id)
            if session is None:
                return fail("session_not_found")
            from ..runtime.chat import get_chat_agent
            regenerate_turn = getattr(get_chat_agent(), "regenerate_turn", None)
            if regenerate_turn is None:
                return fail("history_unavailable")
            checkpoint_id = await regenerate_turn(
                session["agent_id"], session["thread_id"], message_id, new_prompt,
            )
            if checkpoint_id is None:
                return ok(RegenerateSessionOutput(checkpoint_id=None, regenerated=False))
            persisted = _persist_active_checkpoint(session_id, checkpoint_id, expected_revision)
            if not persisted:
                return fail("session_revision_conflict")
            return ok(RegenerateSessionOutput(checkpoint_id=checkpoint_id, regenerated=True))
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
        idempotency_key=f"regenerate:{session_id}:{uuid4().hex}", envelope=envelope,
    )
    structured = raw.get("result", {}).get("structured_content") if isinstance(raw, dict) else None
    if not isinstance(structured, dict):
        raise RuntimeError("session MCP transport failed")
    if structured.get("error") == "session_not_found":
        return None
    if structured.get("ok") is not True:
        raise RuntimeError("session regenerate authorization failed")
    data = structured.get("data")
    return data.get("session") if structured.get("ok") is True and isinstance(data, dict) else None


def _persist_active_checkpoint(session_id: str, checkpoint_id: str, expected_revision: int) -> bool:
    envelope = get_envelope()
    factory = get_service("tool_invoker_for_caller")
    invoker = factory("agent") if callable(factory) else None
    if not callable(invoker):
        raise RuntimeError("agent caller-bound tool invoker is unavailable")
    raw = invoker(
        {"brick_name": "session", "tool_name": "set_active_checkpoint"},
        arguments={
            "session_id": session_id, "checkpoint_id": checkpoint_id,
            "expected_revision": expected_revision, "envelope": envelope,
        },
        idempotency_key=f"regenerate-persist:{session_id}:{uuid4().hex}", envelope=envelope,
    )
    structured = raw.get("result", {}).get("structured_content") if isinstance(raw, dict) else None
    return isinstance(structured, dict) and structured.get("ok") is True


__all__ = ["RegenerateSessionInput", "RegenerateSessionOutput", "register"]
