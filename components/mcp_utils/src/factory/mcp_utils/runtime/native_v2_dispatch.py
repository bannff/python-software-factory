"""Native MCP tool dispatch with authorization and scoped cleanup."""
from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from pydantic import ValidationError

from .elicitation import PrepareReady
from .native_v2_access import authorization_failure, operation
from .schema_migration import SchemaMigrationError
from .tool_result import ToolResult, fail


async def dispatch_call(
    context: Any, params: Any, registrations: dict[str, Any],
    controller: Any, text_content: type[Any],
) -> Any:
    item = registrations.get(getattr(params, "name", None))
    if item is None:
        return generic_failure(text_content)
    token = _authorize(controller, item, text_content)
    if token is False:
        return authorization_failure(text_content)
    arguments = getattr(params, "arguments", None) or {}
    if not isinstance(arguments, Mapping):
        _reset(token)
        return generic_failure(text_content)
    try:
        terminal, protected = await _prepare(context, params, item, arguments, text_content)
        if not isinstance(terminal, dict):
            return terminal
        terminal = _trusted_arguments(item, terminal)
        from .native_v2_instrumentation import invoke_native_tool
        result = await invoke_native_tool(
            getattr(item, "brick_name", None) or "unknown",
            getattr(item, "source_name", None) or item.name,
            item.handler, terminal, protected_override=protected,
            excluded_argument_fields=getattr(
                item, "telemetry_excluded_argument_fields", frozenset(),
            ),
            excluded_envelope_fields=getattr(
                item, "telemetry_excluded_envelope_fields", frozenset(),
            ),
        )
        return project_result(result, text_content)
    except (SchemaMigrationError, ValidationError):
        return invalid_arguments(item.name, text_content)
    except Exception:
        return generic_failure(text_content)
    finally:
        _reset(token)


def _trusted_arguments(item: Any, arguments: dict[str, Any]) -> dict[str, Any]:
    """Project server authority into the tool's declared envelope shape."""
    from ..context import get_envelope
    from .envelope_projection import project_envelope_arguments
    return project_envelope_arguments(
        item.handler, arguments, dict(get_envelope() or {}),
    )


def _authorize(controller: Any, item: Any, text_content: type[Any]) -> Any:
    if controller is None:
        return None
    principal = controller.principal()
    if principal is None or not controller.decide(principal, operation(item, "execute")).allowed:
        return False
    from ..context import set_envelope
    return set_envelope({
        "principal_id": principal.subject, "tenant_id": principal.tenant_id,
        "tool_name": item.name, "attributes": {"client_id": principal.client_id},
    })


def _reset(token: Any) -> None:
    if token not in (None, False):
        from ..context import reset_envelope
        reset_envelope(token)


async def _prepare(context: Any, params: Any, item: Any, arguments: Mapping[str, Any], text: type[Any]) -> tuple[Any, bool]:
    terminal, protected = dict(arguments), False
    prepare = getattr(item, "prepare", None)
    if prepare is None:
        return terminal, protected
    from .native_v2_elicitation import run_preparation
    prepared = await run_preparation(
        item.handler, prepare, terminal, getattr(params, "input_responses", None),
    )
    if not isinstance(prepared, PrepareReady):
        if isinstance(prepared, ToolResult):
            return project_result(prepared, text), False
        if getattr(context, "protocol_version", None) not in (None, "2026-07-28"):
            return project_result(fail("elicitation requires MCP protocol 2026-07-28"), text), False
        return prepared, False
    return dict(prepared.arguments), prepared.protected


def project_result(result: Any, text: type[Any]) -> Any:
    if not isinstance(result, ToolResult):
        raise TypeError("typed MCP handlers must return ToolResult")
    from mcp.types import CallToolResult
    envelope = result.model_dump(mode="json")
    return CallToolResult(
        content=[text(type="text", text=json.dumps(envelope, separators=(",", ":")))],
        structured_content=envelope, is_error=not result.ok,
    )


def invalid_arguments(name: str, text: type[Any]) -> Any:
    from mcp.types import CallToolResult
    return CallToolResult(
        content=[text(type="text", text=f"Invalid arguments for tool '{name}'")], is_error=True,
    )


def generic_failure(text: type[Any]) -> Any:
    return project_result(fail("tool_execution_failed"), text)


__all__ = ["dispatch_call", "generic_failure", "invalid_arguments", "project_result"]
