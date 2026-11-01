"""Agent-side Session MCP adapter for cooperative steering."""
from __future__ import annotations

import os
from dataclasses import replace
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from factory.llm_gateway.interface import configured_chat_model_id
from factory.mcp_utils.interface import get_service

from ..runtime_contracts import RuntimeInvocation

if TYPE_CHECKING:
    # Dormant laziness: langchain imports live in the langgraph-legacy group.
    from .langchain_steering import SteerDelivery


def _process_default_model_id():
    """Same env-driven default the LangChain runtime falls back to.

    Managed invocations carry an empty ``RuntimeInvocation.model_id``; the
    session brick requires a concrete non-empty model. Delegates to the
    gateway's authority (#136), with this literal covering an unset value.
    """
    return configured_chat_model_id() or "us.anthropic.claude-sonnet-4-6"


def _default_project() -> str:
    """Project bound at chat-session creation (COMPANION_X_DEFAULT_PROJECT).

    Every Session row must carry a project or devtools calls fail with
    ``tool_execution_failed``; empty/unset keeps the old unbound behavior.
    """
    return os.environ.get("COMPANION_X_DEFAULT_PROJECT", "").strip()


# Mirrors bases/api ag_ui_input.prefix_context; a title must come from what the
# user typed, not from the context block the API prepends to the prompt.
_CONTEXT_PREFIX = "Canvas context (system-supplied, FE-pushed):"


def session_title(prompt: str) -> str:
    """First line of the user's own message, falling back to ``New chat``."""
    text = prompt.strip()
    if text.startswith(_CONTEXT_PREFIX):
        text = text.partition("\n\n")[2].strip()
    lines = text.splitlines()
    return lines[0][:200] if lines and lines[0] else "New chat"


class SessionSteeringMCP:
    """Resolve and settle steers through caller-bound native MCP only."""

    def bind(self, request: RuntimeInvocation) -> RuntimeInvocation:
        """Owner-scoped Session binding before graph selection: identified
        requests use durable Session authority; local/test paths keep hints."""
        session = self._ensure_session(request)
        if session is None:
            return request
        return replace(
            request, agent_id=str(session["agent_id"]),
            model_id=str(session["model"]),
            memory_scope=str(session.get("memory_scope") or "default"),
            memory_mode=str(session.get("mode") or "persistent"),
            checkpoint_id=session.get("active_checkpoint_id"),
        )

    def ensure(self, request: RuntimeInvocation) -> str | None:
        session = self._ensure_session(request)
        return str(session["session_id"]) if session is not None else None

    def _ensure_session(self, request: RuntimeInvocation) -> dict[str, Any] | None:
        if request.tenant_id is None or request.thread_id is None:
            return None
        title = session_title(request.prompt)
        payload = self._public(
            "ensure_thread", {
                "thread_id": request.thread_id, "title": title,
                "agent_id": request.agent_id,
                "model": request.model_id or _process_default_model_id(),
                "memory_scope": request.memory_scope, "mode": request.memory_mode,
                "project": _default_project(),
                "envelope": self._identity(request),
            }, request,
        )
        if payload is None:
            raise RuntimeError("session registration failed")
        return payload["session"]

    def write(
        self, request: RuntimeInvocation, send_id: str, content: str,
    ) -> SteerDelivery:
        identity = self._identity(request)
        resolved = self._public(
            "resolve_thread", {"thread_id": request.thread_id, "envelope": identity},
            request,
        )
        if resolved is None:
            raise RuntimeError("session registration missing")
        session = resolved["session"]
        payload = self._public(
            "steer", {
                "session_id": session["session_id"], "send_id": send_id,
                "content": content, "envelope": identity,
            }, request,
        )
        if payload is None:
            raise RuntimeError("session steer write failed")
        item = payload["steer"]
        from .langchain_steering import SteerDelivery

        return SteerDelivery(
            tenant_id=item["tenant_id"], owner_id=item["owner_id"],
            session_id=item["session_id"], delivery_id=item["delivery_id"],
            send_id=item["send_id"], content=item["content"], revision=item["revision"],
        )

    def written(self, request: RuntimeInvocation) -> tuple[SteerDelivery, ...]:
        if request.tenant_id is None or request.thread_id is None:
            return ()
        identity = self._identity(request)
        resolved = self._public(
            "resolve_thread", {"thread_id": request.thread_id, "envelope": identity},
            request,
        )
        if resolved is None:
            return ()
        session = resolved["session"]
        if session.get("agent_id") != request.agent_id:
            raise RuntimeError("session agent binding mismatch")
        listed = self._public(
            "list_written_steers",
            {"session_id": session["session_id"], "envelope": identity}, request,
        )
        if listed is None:
            return ()
        from .langchain_steering import SteerDelivery

        return tuple(SteerDelivery(
            tenant_id=item["tenant_id"], owner_id=item["owner_id"],
            session_id=item["session_id"], delivery_id=item["delivery_id"],
            send_id=item["send_id"], content=item["content"], revision=item["revision"],
        ) for item in listed["steers"])

    def consume(self, delivery: SteerDelivery) -> bool:
        return self._settle("acknowledge_steer", delivery)

    def requeue_written(self, request: RuntimeInvocation) -> tuple[str, ...]:
        settled: list[str] = []
        for delivery in self.written(request):
            if self._settle("requeue_steer", delivery):
                settled.append(delivery.delivery_id)
        return tuple(settled)

    def _public(
        self, tool: str, arguments: dict[str, Any], request: RuntimeInvocation,
    ) -> dict[str, Any] | None:
        payload = self._call(
            tool, arguments, self._identity(request),
            f"{request.invocation_id}:{tool}:{uuid4().hex}",
        )
        if payload.get("ok") is True:
            data = payload.get("data")
            return data if isinstance(data, dict) else None
        if payload.get("error") == "session_not_found":
            return None
        raise RuntimeError("session steering read failed")

    def _settle(self, tool: str, delivery: SteerDelivery) -> bool:
        binding = {
            "tenant_id": delivery.tenant_id, "owner_id": delivery.owner_id,
            "session_id": delivery.session_id, "delivery_id": delivery.delivery_id,
            "revision": delivery.revision,
        }
        payload = self._call(
            tool, binding,
            {"tenant_id": delivery.tenant_id, "principal_id": delivery.owner_id},
            f"steer:{delivery.delivery_id}:r{delivery.revision}:{tool}",
            steer=binding,
        )
        if payload.get("ok") is True:
            return True
        if payload.get("error") in {"session_revision_conflict", "session_not_found"}:
            return False
        raise RuntimeError("session steering settlement failed")

    @staticmethod
    def _identity(request: RuntimeInvocation) -> dict[str, str]:
        assert request.tenant_id is not None and request.owner_id is not None
        return {"tenant_id": request.tenant_id, "principal_id": request.owner_id}

    @staticmethod
    def _call(
        tool: str, arguments: dict[str, Any], envelope: dict[str, Any],
        idempotency_key: str, **binding: Any,
    ) -> dict[str, Any]:
        factory = get_service("tool_invoker_for_caller")
        invoker = factory("agent") if callable(factory) else None
        if not callable(invoker):
            raise RuntimeError("agent caller-bound tool invoker is unavailable")
        raw = invoker(
            {"brick_name": "session", "tool_name": tool}, arguments=arguments,
            idempotency_key=idempotency_key, envelope=envelope, **binding,
        )
        if not isinstance(raw, dict) or raw.get("ok") is not True:
            raise RuntimeError("session MCP transport failed")
        structured = raw.get("result", {}).get("structured_content")
        if not isinstance(structured, dict):
            raise RuntimeError("session MCP result is invalid")
        return structured


__all__ = ["SessionSteeringMCP"]
