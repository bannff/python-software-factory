"""Caller-bound capabilities for one provider-neutral managed attempt."""
from __future__ import annotations

from typing import Any

from factory.mcp_utils.interface import get_service

from .execution_manifest import NamedDatasetMCPPort


def _safe_metadata(event: dict[str, Any]) -> dict[str, str]:
    """Provider projection; Workflow never interprets raw provider events."""
    result: dict[str, str] = {}
    for source, target, maximum in (("type", "provider_event_type", 128), ("node_id", "node_id", 256)):
        value = event.get(source)
        if type(value) is str and value and len(value) <= maximum and value.isprintable():
            result[target] = value
    return result


class ManagedServiceCapability:
    def __init__(self, **binding: Any) -> None:
        factory = get_service("tool_invoker_for_caller")
        if not callable(factory) or not callable(factory("agent")):
            raise RuntimeError("agent caller-bound tool invoker is unavailable")
        self._invoke = factory("agent")
        required = {"workflow_run_id", "attempt_id", "revision", "engine_id", "registration_digest", "request_digest", "provider_request_digest"}
        if set(binding) != required:
            raise ValueError("managed execution binding must be complete")
        self.binding = binding
        self._envelope = {"run_id": binding["workflow_run_id"]}

    def _call(self, brick: str, tool: str, arguments: dict[str, Any], *, idempotency_key: str, attempt: bool = False) -> dict[str, Any]:
        result = self._invoke({"brick_name": brick, "tool_name": tool}, arguments=arguments,
            idempotency_key=idempotency_key, envelope=self._envelope,
            **({"attempt": self.binding} if attempt else {}))
        if not isinstance(result, dict) or result.get("ok") is not True:
            raise RuntimeError(f"{brick}.{tool} invocation failed: {result}")
        return result

    def dataset_port(self) -> NamedDatasetMCPPort:
        return NamedDatasetMCPPort(lambda tool, arguments: self._call("dataset", tool, arguments,
            idempotency_key=f"{self.binding['attempt_id']}:r{self.binding['revision']}:dataset:{tool}"))

    async def persist(self, sequence: int, event: dict[str, Any], *, terminal: bool) -> None:
        self._call("workflow", "append_execution_event", {**self.binding, "sequence": sequence,
            "terminal": terminal, "raw_evidence": event, "safe_metadata": _safe_metadata(event)},
            idempotency_key=f"{self.binding['attempt_id']}:r{self.binding['revision']}:event:{sequence}", attempt=True)


__all__ = ["ManagedServiceCapability"]
