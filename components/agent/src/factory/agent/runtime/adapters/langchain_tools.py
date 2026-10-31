"""LangChain tool projection over the scoped capability client."""
from __future__ import annotations

import hashlib
import json
from contextvars import ContextVar
from dataclasses import asdict
from typing import Any

from factory.mcp_utils.interface import (
    bind_capability_scope,
    CapabilityInvocation,
    CapabilityResult,
    CapabilityScope,
    reset_capability_scope,
    ScopedCapabilityClientPort,
)

from ..approval_policy import ApprovalPolicyStore
from ..runtime_contracts import RuntimeInvocation

_CURRENT_INVOCATION: ContextVar[RuntimeInvocation | None] = ContextVar(
    "langchain_runtime_invocation", default=None,
)

# Row 3 (feature-map), owner ruling 2026-09-16 21:20: "Incognito: read
# memory, write nothing; Temporary: read nothing, write nothing, session
# deleted on close." Scoped literally to the memory brick's own tools —
# lessons/KB are unaffected by this session's memory_mode (not part of
# the ruling's wording). The exhaustive tool inventory is pinned by
# ``components/memory/test/factory/memory/test_typed_mcp_boundary.py``'s
# own ``_EXPECTED`` catalog, not guessed: capability/health/schema tools
# (``get_capabilities``, ``memory_get_views``, etc.) touch no memory
# content and are excluded from both sets.
_MEMORY_WRITE_TOOLS = frozenset({
    "memory_store", "memory_delete", "memory_update", "memory_bulk_delete",
    "memory_delete_user", "memory_consolidate", "memory_evolve",
    "memory_embed_backfill", "memory_import_record",
})
_MEMORY_READ_TOOLS = frozenset({
    "memory_get", "memory_recall_inspect", "memory_history",
    "memory_bulk_preview", "memory_list", "memory_retrieve", "memory_stats",
    "memory_hybrid_search", "memory_search_by_time",
})


def bind_invocation(request: RuntimeInvocation):
    """Bind correlation context for capability calls in one Agent turn."""
    return _CURRENT_INVOCATION.set(request)


def reset_invocation(token: Any) -> None:
    """Restore the prior invocation context."""
    _CURRENT_INVOCATION.reset(token)


def _idempotency_key(request: RuntimeInvocation, name: str, arguments: dict[str, Any]) -> str:
    canonical = json.dumps(arguments, sort_keys=True, separators=(",", ":"), default=str)
    digest = hashlib.sha256(f"{request.invocation_id}:{name}:{canonical}".encode()).hexdigest()
    return f"langchain:{digest}"


def _correlation(request: RuntimeInvocation) -> dict[str, str]:
    from factory.mcp_utils.interface import get_envelope

    ambient = get_envelope() or {}
    correlation_id = ambient.get("correlation_id") or request.invocation_id
    values = {
        "invocation_id": request.invocation_id,
        "correlation_id": correlation_id,
        "agent_id": request.agent_id,
        "thread_id": request.thread_id or "",
        "session_id": request.thread_id or "",
        "tenant_id": request.tenant_id or "",
        "principal_id": request.owner_id or "",
        **request.metadata,
    }
    return {key: value for key, value in values.items() if value}


def _approval_decision(
    store: ApprovalPolicyStore | None, request: RuntimeInvocation,
    name: str, arguments: dict[str, Any], tool_call_id: str,
) -> bool:
    """Return approval decision; empty/missing-owner policy preserves autonomy."""
    if store is None or request.tenant_id is None or request.owner_id is None:
        return True
    if name not in store.get(request.tenant_id, request.owner_id).tool_names:
        return True
    import langgraph.types

    preview = json.dumps(arguments, sort_keys=True, default=str)
    reply = langgraph.types.interrupt({
        "_approval_pending": True,
        "interrupt_id": tool_call_id,
        "tool_call_id": tool_call_id,
        "tool": name,
        "command": preview[:300],
    })
    return bool(isinstance(reply, dict) and reply.get("approved") is True)


def _memory_mode_decision(request: RuntimeInvocation, name: str) -> str | None:
    """Row 3 gate — ``None`` when the call is allowed, else the typed
    error to report. Persistent (or an empty/unset mode -- no explicit
    choice was ever made) never restricts anything, matching the row's
    own "explicit per-chat choices win" contract."""
    if request.memory_mode == "temporary":
        if name in _MEMORY_WRITE_TOOLS or name in _MEMORY_READ_TOOLS:
            return "memory_mode_temporary_blocks_memory"
    elif request.memory_mode == "incognito":
        if name in _MEMORY_WRITE_TOOLS:
            return "memory_mode_incognito_blocks_memory_write"
    return None


async def build_langchain_tools(
    client: ScopedCapabilityClientPort, effective_scope: CapabilityScope,
    approval_store: ApprovalPolicyStore | None = None,
) -> list[Any]:
    """Project only effective descriptors and bind exact invocation authority."""
    from langchain_core.tools import StructuredTool

    tools: list[Any] = []
    for descriptor in await client.list_capabilities():
        if descriptor.name not in effective_scope.tool_names:
            continue
        async def invoke_capability(
            _name: str = descriptor.name, **arguments: Any,
        ) -> dict[str, Any]:
            request = _CURRENT_INVOCATION.get()
            if request is None:
                raise RuntimeError("capability called outside a runtime invocation")
            call_id = _idempotency_key(request, _name, arguments)
            mode_denial = _memory_mode_decision(request, _name)
            if mode_denial is not None:
                return asdict(CapabilityResult(
                    content=({"type": "text", "text": "Memory is disabled for this session"},),
                    structured_content={"ok": False, "error": mode_denial},
                    is_error=True,
                ))
            if not _approval_decision(
                approval_store, request, _name, arguments, call_id,
            ):
                return asdict(CapabilityResult(
                    content=({"type": "text", "text": "Tool call denied by owner"},),
                    structured_content={"ok": False, "error": "approval_denied"},
                    is_error=True,
                ))
            token = bind_capability_scope(effective_scope)
            try:
                result = await client.invoke(CapabilityInvocation(
                    name=_name,
                    arguments=arguments,
                    idempotency_key=call_id,
                    correlation=_correlation(request),
                ))
                return asdict(result)
            finally:
                reset_capability_scope(token)

        tools.append(StructuredTool.from_function(
            coroutine=invoke_capability,
            name=descriptor.name,
            description=descriptor.description or descriptor.name,
            args_schema=descriptor.input_schema,
            infer_schema=False,
        ))
    return tools


__all__ = ["bind_invocation", "build_langchain_tools", "reset_invocation"]
