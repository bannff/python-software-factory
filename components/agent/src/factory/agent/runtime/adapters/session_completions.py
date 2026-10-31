"""Agent-side Session MCP adapter for durable completion delivery."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from factory.mcp_utils.interface import get_service

from ..runtime_contracts import RuntimeInvocation


@dataclass(frozen=True)
class CompletionDelivery:
    tenant_id: str
    owner_id: str
    session_id: str
    run_id: str
    outcome: str
    summary: str
    result_digest: str
    revision: int


class SessionCompletionMCP:
    def pending(self, request: RuntimeInvocation) -> tuple[CompletionDelivery, ...]:
        if request.tenant_id is None or request.thread_id is None:
            return ()
        identity = {
            "tenant_id": request.tenant_id, "principal_id": request.owner_id,
        }
        resolved = self._public(
            "resolve_thread", {"thread_id": request.thread_id, "envelope": identity},
            identity, f"completion-origin:{request.invocation_id}:{uuid4().hex}",
        )
        if resolved is None:
            return ()
        listed = self._public(
            "list_pending_completions",
            {"session_id": resolved["session"]["session_id"], "envelope": identity},
            identity, f"completion-list:{request.invocation_id}:{uuid4().hex}",
        )
        return tuple(CompletionDelivery(
            tenant_id=item["tenant_id"], owner_id=item["owner_id"],
            session_id=item["session_id"], run_id=item["run_id"],
            outcome=item["outcome"], summary=item["summary"],
            result_digest=item["result_digest"], revision=item["revision"],
        ) for item in (listed or {}).get("completions", ()))

    def acknowledge(self, delivery: CompletionDelivery) -> bool:
        binding = {
            "tenant_id": delivery.tenant_id, "owner_id": delivery.owner_id,
            "session_id": delivery.session_id, "run_id": delivery.run_id,
            "revision": delivery.revision, "result_digest": delivery.result_digest,
        }
        payload = self._call(
            "acknowledge_completion", binding,
            {"tenant_id": delivery.tenant_id, "principal_id": delivery.owner_id},
            f"completion-ack:{delivery.run_id}:r{delivery.revision}",
            completion=binding,
        )
        return payload.get("ok") is True

    def _public(
        self, tool: str, arguments: dict[str, Any], envelope: dict[str, Any],
        idempotency_key: str,
    ) -> dict[str, Any] | None:
        payload = self._call(tool, arguments, envelope, idempotency_key)
        if payload.get("ok") is True:
            data = payload.get("data")
            return data if isinstance(data, dict) else None
        if payload.get("error") == "session_not_found":
            return None
        raise RuntimeError("session completion read failed")

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
        structured = raw.get("result", {}).get("structured_content") if isinstance(raw, dict) else None
        if not isinstance(structured, dict):
            raise RuntimeError("session completion MCP result is invalid")
        return structured


__all__ = ["CompletionDelivery", "SessionCompletionMCP"]
