"""Scoped-capability → strands tool projection for the chat adapter."""
from __future__ import annotations

import hashlib
import json
from contextvars import ContextVar
from typing import Any

from factory.mcp_utils.interface import (
    bind_capability_scope, CapabilityDescriptor, CapabilityInvocation,
    CapabilityResult, ScopedCapabilityClientPort,
)
from strands.tools.tools import AgentTool
from strands.types._events import ToolResultEvent
from strands.types.tools import ToolResult, ToolUse

from ..runtime_contracts import RuntimeInvocation
from .capability_policy import effective_persona_scope

_CURRENT_INVOCATION: ContextVar[RuntimeInvocation | None] = ContextVar(
    "strands_runtime_invocation", default=None,
)


def bind_invocation(request: RuntimeInvocation):
    """Bind correlation context for capability calls in one Agent turn."""
    return _CURRENT_INVOCATION.set(request)


def reset_invocation(token: Any) -> None:
    """Restore the prior invocation context."""
    _CURRENT_INVOCATION.reset(token)


def _idempotency_key(request: RuntimeInvocation, name: str, arguments: dict[str, Any]) -> str:
    canonical = json.dumps(arguments, sort_keys=True, separators=(",", ":"), default=str)
    digest = hashlib.sha256(f"{request.invocation_id}:{name}:{canonical}".encode()).hexdigest()
    return f"strands:{digest}"


def _correlation(request: RuntimeInvocation) -> dict[str, str]:
    from factory.mcp_utils.interface import get_envelope

    ambient = get_envelope() or {}
    values = {
        "invocation_id": request.invocation_id,
        "correlation_id": ambient.get("correlation_id") or request.invocation_id,
        "agent_id": request.agent_id,
        "thread_id": request.thread_id or "",
        "session_id": request.thread_id or "",
        "tenant_id": request.tenant_id or "",
        "principal_id": request.owner_id or "",
    }
    return {key: value for key, value in values.items() if value}


def _tool_result(tool_use: ToolUse, result: CapabilityResult) -> ToolResult:
    text = json.dumps(
        result.structured_content if result.structured_content is not None
        else list(result.content),
        default=str,
    )
    return {
        "toolUseId": str(tool_use.get("toolUseId", "")),
        "status": "error" if result.is_error else "success",
        "content": [{"text": text}],
    }


class _CapabilityAgentTool(AgentTool):
    """One scoped capability projected as a strands ``AgentTool``.

    Mirrors the langchain projection (``langchain_tools.py``): the
    invocation contextvar supplies correlation, the effective scope is
    bound around the client call, and the structured result rides the
    stream for the ``structured_payload`` unwrap.
    """

    def __init__(
        self, client: ScopedCapabilityClientPort, effective_scope: Any,
        descriptor: CapabilityDescriptor,
    ) -> None:
        super().__init__()
        self._client = client
        self._scope = effective_scope
        self._descriptor = descriptor

    @property
    def tool_name(self) -> str:
        return self._descriptor.name

    @property
    def tool_spec(self) -> dict[str, Any]:
        return {
            "name": self._descriptor.name,
            "description": self._descriptor.description or self._descriptor.name,
            "inputSchema": {"json": self._descriptor.input_schema},
        }

    @property
    def tool_type(self) -> str:
        return "capability"

    async def stream(  # type: ignore[override]
        self, tool_use: ToolUse, invocation_state: dict[str, Any], **_: Any,
    ) -> Any:
        del invocation_state
        request = _CURRENT_INVOCATION.get()
        if request is None:
            raise RuntimeError("capability called outside a runtime invocation")
        arguments = dict(tool_use.get("input", {}))
        call_id = _idempotency_key(request, self._descriptor.name, arguments)
        token = bind_capability_scope(self._scope)
        try:
            result = await self._client.invoke(CapabilityInvocation(
                name=self._descriptor.name,
                arguments=arguments,
                idempotency_key=call_id,
                correlation=_correlation(request),
            ))
            yield ToolResultEvent(_tool_result(tool_use, result))
        finally:
            from factory.mcp_utils.interface import reset_capability_scope
            reset_capability_scope(token)


async def build_thread_agent_tools(
    client: ScopedCapabilityClientPort, persona: Any,
) -> list[AgentTool]:
    """Discover and project the persona's effective scoped capabilities."""
    effective = effective_persona_scope(client.scope, persona)
    descriptors = await client.list_capabilities()
    return [
        _CapabilityAgentTool(client, effective, descriptor)
        for descriptor in descriptors
        if descriptor.name in effective.tool_names
    ]


__all__ = ["_CURRENT_INVOCATION", "build_thread_agent_tools"]
