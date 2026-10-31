"""Transport-neutral catalog dispatch and result helpers."""
from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from factory.mcp_utils.interface import (
    PROTECTED_OPERATION_ERROR_MESSAGE, PROTECTED_OPERATION_ERROR_TYPE,
    invoke_native_tool, is_protected_operation,
)

logger = logging.getLogger(__name__)


def resolve_tool_name(
    tools: Mapping[str, Any], brick_name: str, requested_name: str,
) -> str | None:
    """Resolve local, prefixed, dotted, or canonical native-v2 spellings."""
    for candidate in (
        requested_name, f"{brick_name}_{requested_name}", f"{brick_name}.{requested_name}",
    ):
        if candidate in tools:
            return candidate
    from .name_resolution import canonical_tool_name
    requested_public = (
        requested_name
        if requested_name.startswith((f"{brick_name}_", f"{brick_name}."))
        else f"{brick_name}_{requested_name}"
    ).replace(".", "_")
    for source_name in tools:
        if canonical_tool_name(brick_name, source_name) == requested_public:
            return source_name
    return None


def transport_failure(
    error_type: str, message: str, *, protected: bool = False,
) -> dict[str, Any]:
    if protected:
        return {"ok": False, "error": {
            "type": PROTECTED_OPERATION_ERROR_TYPE,
            "message": PROTECTED_OPERATION_ERROR_MESSAGE,
        }}
    return {"ok": False, "error": {"type": error_type, "message": message}}


async def invoke_catalog_tool(
    tool: Any, brick_name: str, resolved_name: str,
    arguments: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Invoke one catalog handler with service-boundary and redaction semantics."""
    call_args = arguments or {}
    protected = is_protected_operation(resolved_name, call_args)
    state = None
    stage = "begin_service_invocation"
    try:
        from factory.mcp_utils.interface import (
            acquire_service_entry, begin_service_invocation, end_service_invocation,
        )
        state = begin_service_invocation(
            tool, audience=brick_name, target_tool=resolved_name, arguments=call_args,
        )
        invoke_args = dict(call_args)
        if state is not None:
            invoke_args["_service_entry_authorization"] = acquire_service_entry(tool.fn)
        stage = "invoke_native_tool"
        result = await invoke_native_tool(
            brick_name, resolved_name, tool.fn, invoke_args,
        )
        stage = "serialize_result"
        structured = result.model_dump(mode="json") if hasattr(result, "model_dump") else result
        return {"ok": True, "result": {
            "kind": "tool", "structured_content": structured,
            "content": [], "meta": {},
        }}
    except Exception as exc:
        from factory.mcp_utils.interface import ServiceOnlyAccessError, get_envelope
        if isinstance(exc, ServiceOnlyAccessError):
            return transport_failure(type(exc).__name__, str(exc))
        envelope = get_envelope() or {}
        present_keys = sorted(key for key, value in envelope.items() if value is not None)
        logger.warning(
            "catalog_tool_execution_failed brick=%s tool=%s stage=%s error_type=%s "
            "envelope_keys=%s",
            brick_name, resolved_name, stage, type(exc).__name__, present_keys,
        )
        return transport_failure(
            "ToolExecutionError", "tool_execution_failed", protected=protected,
        )
    finally:
        if state is not None:
            end_service_invocation(state)


def unwrap_transport(envelope: dict[str, Any]) -> Any:
    if not envelope.get("ok"):
        return {"error": envelope["error"]["message"]}
    result = envelope["result"]
    return result["task"] if result.get("kind") == "task" else result.get("structured_content")


__all__ = [
    "invoke_catalog_tool", "resolve_tool_name", "transport_failure", "unwrap_transport",
]
