"""Correlation context helpers for AG-UI chat-originated runs.

The browser ``runId`` is a chat correlation value, not durable Workflow
authority.  Downstream work therefore receives it only as ``correlation_id``;
``run_id`` remains reserved for a persisted Workflow run.
"""
from __future__ import annotations

from contextvars import Token
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CorrelationScope:
    """Tokens required to restore one AG-UI request's ContextVars."""

    envelope_token: Token | None
    caller_hint_token: Token | None


def build_tool_context(thread_id: str, run_id: str, agg: Any) -> dict[str, Any]:
    """Build legacy ``agent_reason`` context without granting run authority."""
    context: dict[str, Any] = {
        "thread_id": thread_id,
        "chat_run_id": run_id,
        "correlation_id": run_id,
    }
    if agg is not None:
        try:
            context["available_tools"] = agg.get_all_tool_names()
        except Exception:
            pass
    return context


def set_correlation_context(thread_id: str, run_id: str) -> CorrelationScope:
    """Scope chat session/correlation fields for one SSE request."""
    envelope_token: Token | None = None
    caller_hint_token: Token | None = None
    try:
        from factory.mcp_utils.interface import push_envelope_updates

        envelope_token = push_envelope_updates(
            session_id=thread_id, correlation_id=run_id,
        )
    except Exception:
        pass
    try:
        from factory.mcp_utils.interface import set_caller_hint

        caller_hint_token = set_caller_hint(f"chat:{thread_id[:8]}")
    except Exception:
        pass
    return CorrelationScope(envelope_token, caller_hint_token)


def clear_correlation_context(scope: CorrelationScope | None) -> None:
    """Restore the enclosing request context after the AG-UI run completes."""
    if scope is None:
        return
    try:
        if scope.caller_hint_token is not None:
            scope.caller_hint_token.var.reset(scope.caller_hint_token)
    except Exception:
        pass
    try:
        from factory.mcp_utils.interface import reset_envelope

        reset_envelope(scope.envelope_token)
    except Exception:
        pass
