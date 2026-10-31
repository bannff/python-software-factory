"""Caller-bound composition adapter for native-envelope invocation."""
from __future__ import annotations

from typing import Any

from factory.mcp_utils.interface import get_service

from .envelope import Envelope
from .models import ToolTarget


class ServiceToolInvoker:
    def __init__(self, callback: Any):
        self._callback = callback

    def invoke(
        self, *, target: ToolTarget, arguments: dict[str, Any],
        idempotency_key: str, envelope: Envelope,
        attempt: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        kwargs = {
            "arguments": arguments, "idempotency_key": idempotency_key,
            "envelope": envelope.model_dump(mode="json"),
        }
        if attempt is not None:
            kwargs["attempt"] = attempt
        return self._callback(target.model_dump(mode="json"), **kwargs)


def resolve_tool_invoker() -> ServiceToolInvoker | None:
    factory = get_service("tool_invoker_for_caller")
    if factory is None:
        return None
    if not callable(factory):
        raise RuntimeError("tool_invoker_for_caller service is not callable")
    callback = factory("workflow")
    if not callable(callback):
        raise RuntimeError("workflow caller-bound tool invoker is unavailable")
    return ServiceToolInvoker(callback)
