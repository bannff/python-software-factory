"""Central observability wrapper for every native MCP-v2 tool invocation."""
from __future__ import annotations

import inspect
import time
from contextvars import ContextVar
from typing import Any, Callable
from uuid import uuid4

from .. import event_bus
from ..context import get_envelope
from ..protected_persistence import (
    is_protected_operation,
    safe_exception,
    telemetry_projection,
)
from ..registry import get_service

try:
    from opentelemetry import trace
    from opentelemetry.trace import StatusCode
    _TRACER = trace.get_tracer("factory.native_mcp_v2")
except ImportError:  # pragma: no cover - optional runtime
    _TRACER = None

_INVOCATION: ContextVar[str | None] = ContextVar("native_mcp_v2_invocation", default=None)


def catalog_identity(catalog_name: str, tool_name: str) -> tuple[str, str]:
    """Derive stable brick/local names for direct catalog calls."""
    brick = catalog_name.removesuffix("-brick").removesuffix("-catalog")
    if brick.startswith("factory-"):
        brick = "mcp_server"
    if not brick or brick in {"root", "test"}:
        brick = tool_name.split(".", 1)[0].split("_", 1)[0] or "unknown"
    return brick, tool_name


async def invoke_native_tool(
    brick_name: str,
    tool_name: str,
    fn: Callable[..., Any],
    arguments: dict[str, Any],
    *,
    protected_override: bool = False,
    excluded_argument_fields: frozenset[str] = frozenset(),
    excluded_envelope_fields: frozenset[str] = frozenset(),
) -> Any:
    """Invoke once and publish one start plus one terminal lifecycle event."""
    started = time.perf_counter()
    invocation_id = uuid4().hex
    context = _context()
    token = _INVOCATION.set(invocation_id)
    protected = protected_override or is_protected_operation(tool_name, arguments)
    telemetry_arguments = _filter_arguments(
        arguments, excluded_argument_fields | excluded_envelope_fields,
    )
    _publish("start", invocation_id, brick_name, tool_name, context,
             arguments=telemetry_arguments, protected=protected)
    span_cm = _span(brick_name, tool_name, invocation_id, context)
    try:
        with span_cm as span:
            try:
                result = fn(**arguments)
                if inspect.isawaitable(result):
                    result = await result
                success = bool(getattr(result, "ok", True))
                if span is not None:
                    span.set_attribute("tool.status", "ok" if success else "error")
                _terminal("result", invocation_id, brick_name, tool_name, context,
                          started, success, telemetry_arguments, result, None, protected)
                return result
            except Exception as exc:
                if span is not None:
                    span.set_status(StatusCode.ERROR)
                    span.record_exception(safe_exception(exc))
                _terminal("error", invocation_id, brick_name, tool_name, context,
                          started, False, telemetry_arguments, None, exc, protected)
                raise
    finally:
        _INVOCATION.reset(token)


def _filter_arguments(
    arguments: dict[str, Any], excluded_fields: frozenset[str],
) -> dict[str, Any]:
    """Project telemetry fields without mutating handler arguments."""
    return {
        key: value for key, value in arguments.items()
        if key not in excluded_fields
    }


def _context() -> dict[str, Any]:
    env = get_envelope() or {}
    correlation = env.get("correlation_id") or env.get("request_id")
    run_id = env.get("workflow_run_id") or env.get("run_id")
    return {
        "caller": env.get("principal_id") or env.get("agent_id") or "unknown",
        "session_id": env.get("session_id"),
        "workflow_run_id": run_id,
        "correlation_id": correlation or run_id,
        "parent_invocation_id": _INVOCATION.get(),
    }


def _span(brick: str, tool: str, invocation_id: str, context: dict[str, Any]):
    if _TRACER is None:
        return _NullSpan()
    attributes = {"brick.name": brick, "tool.name": tool,
                  "tool.invocation_id": invocation_id}
    if context.get("correlation_id"):
        attributes["correlation.id"] = context["correlation_id"]
    return _TRACER.start_as_current_span(f"brick.tool.{brick}.{tool}", attributes=attributes)


def _terminal(phase: str, invocation_id: str, brick: str, tool: str,
              context: dict[str, Any], started: float, success: bool,
              arguments: dict[str, Any], result: Any, exc: Exception | None,
              protected: bool) -> None:
    latency_ms = (time.perf_counter() - started) * 1000.0
    _publish(phase, invocation_id, brick, tool, context, success=success,
             latency_ms=latency_ms, arguments=arguments, result=result,
             exc=exc, protected=protected)
    sink = get_service("tool_invocation_sink")
    if callable(sink):
        try:
            sink(brick, tool, success=success, latency_ms=latency_ms,
                 error=type(exc).__name__ if exc else None,
                 args_summary=telemetry_projection(arguments, protected=protected) or None,
                 caller=context["caller"],
                 result_summary=_result_projection(result, success, protected))
        except Exception:
            pass


def _publish(phase: str, invocation_id: str, brick: str, tool: str,
             context: dict[str, Any], *, success: bool | None = None,
             latency_ms: float = 0.0, arguments: dict[str, Any] | None = None,
             result: Any = None, exc: Exception | None = None,
             protected: bool = False) -> None:
    event: dict[str, Any] = {
        "phase": phase, "invocation_id": invocation_id, "brick": brick,
        "tool": tool, "success": success if success is not None else True,
        "latency_ms": latency_ms, "ts": time.time(),
        "args_summary": telemetry_projection(arguments or {}, protected=protected),
    }
    event.update({key: value for key, value in context.items() if value})
    if phase != "start":
        event["result_summary"] = _result_projection(result, bool(success), protected)
    if exc is not None:
        event["error_type"] = type(exc).__name__
    event_bus.publish(event)


def _result_projection(result: Any, success: bool, protected: bool) -> dict[str, Any]:
    summary = telemetry_projection(result, protected=protected) if result is not None else {}
    return {**summary, "status": "ok" if success else "error"}


class _NullSpan:
    def __enter__(self) -> None:
        return None

    def __exit__(self, *_: Any) -> None:
        return None


__all__ = ["catalog_identity", "invoke_native_tool"]
