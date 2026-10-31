"""Stop a session's currently running turn from outside it (row 61)."""
from __future__ import annotations

import asyncio
from typing import Any, Callable

from factory.mcp_utils.interface import ToolResult, fail, get_service, ok, operational
from factory.mcp_utils.registration import typed_tool

from ..runtime.errors import SessionConflictError, SessionIdentityError, SessionNotFoundError
from .lifecycle_contracts import RevisionSessionInput, StopOutput
from .lifecycle_support import identity


async def _cancel_turn(thread_id: str, envelope: dict[str, Any]) -> bool:
    """Cross-brick call to agent.cancel_turn via the shared invoker seam —
    no direct import; the Agent runtime owns turn cancellation."""
    factory = get_service("tool_invoker_for_caller")
    invoker = factory("session") if callable(factory) else None
    if not callable(invoker):
        return False
    raw = await asyncio.to_thread(
        invoker, {"brick_name": "agent", "tool_name": "agent.cancel_turn"},
        arguments={"thread_id": thread_id}, idempotency_key=None, envelope=envelope,
    )
    if not isinstance(raw, dict) or raw.get("ok") is not True:
        return False
    structured = raw.get("result", {}).get("structured_content")
    if not isinstance(structured, dict) or structured.get("ok") is not True:
        return False
    data = structured.get("data")
    return bool(isinstance(data, dict) and data.get("cancelled"))


def register(mcp: Any, get_runtime: Callable[[], Any]) -> None:
    @typed_tool(mcp)
    @operational(input_model=RevisionSessionInput, output_model=StopOutput, idempotent=False)
    async def session_stop(
        session_id: str, expected_revision: int,
        envelope: dict[str, Any] | None = None,
    ) -> ToolResult[StopOutput]:
        """Cancel the running turn for this session, if any is currently live."""
        runtime = get_runtime().lifecycle
        try:
            tenant_id, owner_id = identity(runtime, envelope)
            record = runtime.get(tenant_id, owner_id, session_id)
            # Advisory, not a mutation guard: session_stop never writes the
            # session record, so a race here is harmless — cancel is idempotent.
            if record.revision != expected_revision:
                raise SessionConflictError
        except SessionIdentityError:
            return fail("session_identity_required")
        except SessionNotFoundError:
            return fail("session_not_found")
        except SessionConflictError:
            return fail("session_revision_conflict")
        cancelled = await _cancel_turn(record.thread_id, envelope or {
            "tenant_id": tenant_id, "principal_id": owner_id,
        })
        return ok(StopOutput(session_id=session_id, cancelled=cancelled))


__all__ = ["register"]
