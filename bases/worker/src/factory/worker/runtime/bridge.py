"""Public MCP gateway bridge with a principal-aware default-deny policy."""
from __future__ import annotations

import logging
from typing import Any

from factory.mcp_utils.interface import is_bounded_json, to_plain_json

from .bridge_policy import BridgePolicy, resolve_principal

logger = logging.getLogger(__name__)
_VALID_CATEGORIES = frozenset({"deterministic", "operational", "authoring"})

# Lazy-cached public MCPAggregator instance. Lifecycle redesign is separate.
_mcp_server: Any = None


def _get_mcp_server() -> Any:
    """Resolve the public aggregator without touching FastMCP internals."""
    global _mcp_server
    if _mcp_server is None:
        from factory.mcp_server.interface import get_aggregator, get_server

        _mcp_server = get_aggregator()
        if _mcp_server is None:
            get_server()
            _mcp_server = get_aggregator()
    return _mcp_server


def _available_tools(aggregator: Any) -> list[str]:
    """Read names through the aggregator's public catalog method."""
    names = aggregator.get_all_tool_names()
    if (
        not isinstance(names, list)
        or len(names) > 1_024
        or not all(isinstance(name, str) and 0 < len(name) <= 256 for name in names)
    ):
        raise TypeError("invalid bridge tool catalog")
    return sorted(set(names))


def _tool_metadata() -> dict[str, dict[str, Any]] | None:
    """Read category and parameter metadata through the public catalog API.

    Category metadata is an authorization input, not advisory discovery data.
    A missing or malformed catalog is therefore unavailable rather than empty.
    """
    try:
        from factory.mcp_server.interface import get_tool_catalog

        payload = get_tool_catalog()
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    entries = payload.get("tools")
    if not isinstance(entries, list):
        return None
    metadata: dict[str, dict[str, Any]] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        for key in ("name", "qualified_name"):
            name = entry.get(key)
            if isinstance(name, str) and name:
                metadata[name] = entry
    return metadata


def _merge_positional(
    tool_name: str,
    positional: list[Any],
    keyword_args: dict[str, Any],
    metadata: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    """Map legacy task positional arguments to the public MCP schema."""
    if not positional:
        return dict(keyword_args)
    entry = metadata.get(tool_name)
    properties = entry.get("input_schema", {}).get("properties", {}) if entry else {}
    if not isinstance(properties, dict) or len(positional) > len(properties):
        return None
    merged = dict(keyword_args)
    for parameter, value in zip(properties, positional):
        if parameter in merged:
            return None
        merged[parameter] = value
    return merged


def _failed_result(value: Any) -> bool:
    """Recognize raw and typed failures without rejecting ``error: null``."""
    if not isinstance(value, dict):
        return False
    if value.get("ok") is False:
        return True
    if value.get("ok") is True:
        return value.get("error") not in (None, "")
    return bool(value.get("error"))


def _failure(tool_name: str | None, code: str) -> dict[str, Any]:
    result: dict[str, Any] = {"error": code}
    if tool_name is not None:
        result["tool"] = tool_name
    return result


def execute_mcp_tool(
    tool_name: str,
    arguments: dict[str, Any] | None = None,
    *,
    positional_args: list[Any] | None = None,
    principal_id: str | None = None,
    policy: BridgePolicy | None = None,
) -> dict[str, Any]:
    """Execute one allowlisted tool through ``MCPAggregator.invoke_tool``."""
    if not isinstance(tool_name, str) or not tool_name or len(tool_name) > 256:
        return _failure(None, "bridge_access_denied")
    keyword_args = {} if arguments is None else arguments
    positional = [] if positional_args is None else positional_args
    if (
        not isinstance(keyword_args, dict)
        or not is_bounded_json(keyword_args)
        or not isinstance(positional, list)
        or not is_bounded_json(positional)
    ):
        return _failure(tool_name, "bridge_arguments_invalid")

    active_policy = policy or BridgePolicy.from_env()
    principal = resolve_principal(principal_id)
    if not active_policy.decide(tool_name, principal).allowed:
        return _failure(tool_name, "bridge_access_denied")

    try:
        aggregator = _get_mcp_server()
        if aggregator is None:
            return _failure(tool_name, "bridge_unavailable")
        names = _available_tools(aggregator)
        metadata = _tool_metadata()
        if metadata is None:
            return _failure(tool_name, "bridge_unavailable")
    except Exception:
        logger.warning("Worker bridge catalog unavailable", exc_info=False)
        return _failure(tool_name, "bridge_unavailable")

    if tool_name not in names:
        return _failure(tool_name, "bridge_tool_not_found")
    entry = metadata.get(tool_name)
    if (
        not isinstance(entry, dict)
        or entry.get("category") not in _VALID_CATEGORIES
    ):
        return _failure(tool_name, "bridge_access_denied")
    category = entry["category"]
    if not active_policy.decide(tool_name, principal, category=category).allowed:
        return _failure(tool_name, "bridge_access_denied")
    call_args = _merge_positional(tool_name, positional, keyword_args, metadata)
    if call_args is None:
        return _failure(tool_name, "bridge_positional_args_invalid")

    try:
        result = aggregator.invoke_tool(tool_name, **call_args)
        plain = to_plain_json(result)
        if not is_bounded_json(plain):
            return _failure(tool_name, "bridge_result_unavailable")
        if _failed_result(plain):
            return _failure(tool_name, "bridge_invocation_failed")
        return {"tool": tool_name, "result": plain}
    except Exception:
        logger.warning("Worker bridge invocation failed: tool=%s", tool_name, exc_info=False)
        return _failure(tool_name, "bridge_invocation_failed")


def list_mcp_tools(
    *,
    principal_id: str | None = None,
    policy: BridgePolicy | None = None,
) -> dict[str, Any]:
    """List exactly the tools executable under the same bridge policy."""
    active_policy = policy or BridgePolicy.from_env()
    principal = resolve_principal(principal_id)
    if not active_policy.allowlist:
        return {"tools": [], "count": 0, "error": "bridge_access_denied"}
    try:
        aggregator = _get_mcp_server()
        if aggregator is None:
            return {"tools": [], "count": 0, "error": "bridge_unavailable"}
        names = _available_tools(aggregator)
        metadata = _tool_metadata()
        if metadata is None:
            return {"tools": [], "count": 0, "error": "bridge_unavailable"}
    except Exception:
        logger.warning("Worker bridge catalog unavailable", exc_info=False)
        return {"tools": [], "count": 0, "error": "bridge_unavailable"}

    visible = []
    for name in names:
        entry = metadata.get(name)
        if (
            not isinstance(entry, dict)
            or entry.get("category") not in _VALID_CATEGORIES
        ):
            continue
        if active_policy.decide(name, principal, category=entry["category"]).allowed:
            visible.append(name)
    matched = [name for name in names if name in active_policy.allowlist]
    error = "bridge_access_denied" if matched and not visible else None
    return {"tools": visible, "count": len(visible), "error": error}


def register_mcp_tasks(celery_app) -> None:
    """Register generic bridge tasks on a Celery app."""

    @celery_app.task(name="factory.execute_tool", bind=True)
    def execute_tool_task(self, tool_name: str, arguments: dict | None = None):
        """Generic Celery task for one public bridge invocation."""
        return execute_mcp_tool(tool_name, arguments)

    @celery_app.task(name="factory.list_tools")
    def list_tools_task():
        """Generic Celery task for the policy-filtered bridge catalog."""
        return list_mcp_tools()

    logger.info("MCP bridge tasks registered on Celery app")


__all__ = ["execute_mcp_tool", "list_mcp_tools", "register_mcp_tasks"]
