"""Shared durable fake state for public-runtime restart properties."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class ProcessCrash(BaseException):
    """Simulate death after an external commit but before journal commit."""


@dataclass
class InvokerState:
    responses: dict[str, dict[str, Any]] = field(default_factory=dict)
    calls: list[tuple[Any, dict[str, Any], str, Any]] = field(default_factory=list)
    commit_counts: dict[str, int] = field(default_factory=dict)
    crashed: bool = False
    consume_attempts: int = 0
    wrapper_count: int = 0


class IdempotentInvoker:
    """Fresh port wrapper around durable fake external-system state."""

    def __init__(self, state: InvokerState):
        self.state = state
        state.wrapper_count += 1

    @staticmethod
    def _success(target: Any, arguments: dict[str, Any]) -> tuple[dict, dict]:
        digest = "a" * 64
        output = {"value": arguments.get("value", 1)}
        if target.tool_name == "produce":
            output["artifacts"] = {"item": {
                "uri": "file:///item", "sha256": digest,
                "evidence": {"sha256": digest},
            }}
        response = {"ok": True, "result": {
            "kind": "tool", "content": [], "meta": {},
            "structured_content": output,
        }}
        return output, response

    def invoke(self, *, target: Any, arguments: dict[str, Any],
               idempotency_key: str, envelope: Any) -> dict[str, Any]:
        state = self.state
        state.calls.append((target, arguments, idempotency_key, envelope))
        if idempotency_key in state.responses:
            return state.responses[idempotency_key]
        if target.tool_name == "consume" and state.consume_attempts == 0:
            state.consume_attempts += 1
            response = {"ok": False, "error": {
                "type": "ServiceUnavailable", "message": "temporarily unavailable",
            }}
            state.responses[idempotency_key] = response
            return response
        _, response = self._success(target, arguments)
        state.responses[idempotency_key] = response
        state.commit_counts[idempotency_key] = state.commit_counts.get(idempotency_key, 0) + 1
        if target.tool_name == "produce" and not state.crashed:
            state.crashed = True
            raise ProcessCrash("after external commit")
        return response
