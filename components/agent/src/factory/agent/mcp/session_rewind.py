"""Authorized Agent-owned transcript rewind (row 15, feature-map).

"Drop the transcript back to an earlier turn" — unlike regenerate (row
16), rewind generates NOTHING new: it finds the checkpoint right after
the target message landed and persists it as the thread's "current"
branch via the SAME ``session_set_active_checkpoint`` primitive row 16
already built. Mirrors ``session_fork_transcript.py``'s exact
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


class RewindSessionInput(StrictDTO):
    session_id: str = Field(min_length=1, max_length=128)
    message_id: str = Field(min_length=1, max_length=128)
    expected_revision: int = Field(ge=1)


class RewindSessionOutput(StrictDTO):
    checkpoint_id: str | None = None
    rewound: bool


def register(mcp: Any) -> None:
    @mcp.tool()
    @operational(input_model=RewindSessionInput, output_model=RewindSessionOutput,
                 idempotent=False)
    async def session_rewind(
        session_id: str, message_id: str, expected_revision: int,
    ) -> ToolResult[RewindSessionOutput]:
        try:
            session = _authorized_session(session_id)
            if session is None:
                return fail("session_not_found")
            from ..runtime.chat import get_chat_agent
            rewind_to_message = getattr(get_chat_agent(), "rewind_to_message", None)
            if rewind_to_message is None:
                return fail("history_unavailable")
            checkpoint_id = await rewind_to_message(
                session["agent_id"], session["thread_id"], message_id,
            )
            if checkpoint_id is None:
                return ok(RewindSessionOutput(checkpoint_id=None, rewound=False))
            persisted = _persist_active_checkpoint(session_id, checkpoint_id, expected_revision)
            if not persisted:
                return fail("session_revision_conflict")
            return ok(RewindSessionOutput(checkpoint_id=checkpoint_id, rewound=True))
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
        idempotency_key=f"rewind:{session_id}:{uuid4().hex}", envelope=envelope,
    )
    structured = raw.get("result", {}).get("structured_content") if isinstance(raw, dict) else None
    if not isinstance(structured, dict):
        raise RuntimeError("session MCP transport failed")
    if structured.get("error") == "session_not_found":
        return None
    if structured.get("ok") is not True:
        raise RuntimeError("session rewind authorization failed")
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
        idempotency_key=f"rewind-persist:{session_id}:{uuid4().hex}", envelope=envelope,
    )
    structured = raw.get("result", {}).get("structured_content") if isinstance(raw, dict) else None
    return isinstance(structured, dict) and structured.get("ok") is True


__all__ = ["RewindSessionInput", "RewindSessionOutput", "register"]
