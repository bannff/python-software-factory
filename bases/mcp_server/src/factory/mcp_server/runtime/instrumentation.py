"""Thin OTel tracing for brick tool calls. No-ops without opentelemetry."""
from __future__ import annotations

import time
from typing import Any, Callable

from factory.mcp_utils.interface import event_bus, safe_exception, telemetry_projection

from . import graph_sink

try:
    from opentelemetry import trace
    from opentelemetry.instrumentation.utils import is_instrumentation_enabled
    from opentelemetry.trace import StatusCode
    _tracer = trace.get_tracer("factory.mcp_server")
    _HAS_OTEL = True
except ImportError:
    _tracer = None  # type: ignore[assignment]
    _HAS_OTEL = False


def _summarize_args(kwargs: dict) -> dict[str, Any]:
    """Allowlist-only argument projection; never serialize arbitrary values."""
    return telemetry_projection(kwargs)


def _summarize_result(result: Any) -> dict[str, Any]:
    """Allowlist-only result projection; status and counts stay observable."""
    summary = telemetry_projection(result)
    if isinstance(result, dict):
        summary["status"] = "error" if result.get("error") else "ok"
    else:
        summary["status"] = "ok"
    return summary


def _read_live_context() -> tuple[str, str | None, str | None]:
    try:
        from factory.mcp_utils.interface import get_envelope
        env = get_envelope() or {}
        caller = env.get("principal_id") or env.get("agent_id") or "unknown"
        workflow_run_id = env.get("workflow_run_id") or env.get("run_id")
        if workflow_run_id is None:
            try:
                from factory.mcp_server.interface import get_workflow_run_id
                workflow_run_id = get_workflow_run_id()
            except Exception:
                pass
        return caller, env.get("session_id"), workflow_run_id
    except Exception:
        return "unknown", None, None


def _span(brick: str, tool: str):
    return _tracer.start_as_current_span(
        f"brick.tool.{brick}.{tool}",
        attributes={"brick.name": brick, "tool.name": tool},
    )


async def traced_tool_call(
    brick_name: str, tool_name: str, fn: Callable, kwargs: dict,
    result_for_summary: Callable[[Any], Any] | None = None,
) -> Any:
    t0 = time.perf_counter()
    if not _HAS_OTEL or not is_instrumentation_enabled():
        try:
            result = fn(**kwargs)
            result = await result if hasattr(result, "__await__") else result
            _emit(brick_name, tool_name, True, t0, kwargs=kwargs,
                  result=result_for_summary(result) if result_for_summary else result)
            return result
        except Exception as exc:
            _emit(brick_name, tool_name, False, t0, exc, kwargs=kwargs)
            raise
    with _span(brick_name, tool_name) as span:
        try:
            result = fn(**kwargs)
            result = await result if hasattr(result, "__await__") else result
            span.set_attribute("tool.status", "ok")
            _emit(brick_name, tool_name, True, t0, kwargs=kwargs,
                  result=result_for_summary(result) if result_for_summary else result)
            return result
        except Exception as exc:
            span.set_status(StatusCode.ERROR)
            span.record_exception(safe_exception(exc))
            _emit(brick_name, tool_name, False, t0, exc, kwargs=kwargs)
            raise


def traced_tool_call_sync(brick_name: str, tool_name: str, fn: Callable, kwargs: dict) -> Any:
    from .pools import _run_sync_agent
    t0 = time.perf_counter()
    if not _HAS_OTEL or not is_instrumentation_enabled():
        try:
            result = fn(**kwargs)
            result = _run_sync_agent(result) if hasattr(result, "__await__") else result
            _emit(brick_name, tool_name, True, t0, kwargs=kwargs, result=result)
            return result
        except Exception as exc:
            _emit(brick_name, tool_name, False, t0, exc, kwargs=kwargs)
            raise
    with _span(brick_name, tool_name) as span:
        try:
            result = fn(**kwargs)
            result = _run_sync_agent(result) if hasattr(result, "__await__") else result
            span.set_attribute("tool.status", "ok")
            _emit(brick_name, tool_name, True, t0, kwargs=kwargs, result=result)
            return result
        except Exception as exc:
            span.set_status(StatusCode.ERROR)
            span.record_exception(safe_exception(exc))
            _emit(brick_name, tool_name, False, t0, exc, kwargs=kwargs)
            raise


def _emit(brick_name: str, tool_name: str, success: bool, t0: float,
          exc: Exception | None = None, *, kwargs: dict | None = None,
          result: Any = None) -> None:
    """Send projections, never raw tool values or exception text, to sinks."""
    caller, session_id, workflow_run_id = _read_live_context()
    args_summary = _summarize_args(kwargs or {})
    result_summary = _summarize_result(result) if result is not None else None
    error = type(exc).__name__ if exc else None
    latency_ms = (time.perf_counter() - t0) * 1000.0
    try:
        graph_sink.materialize(brick_name, tool_name, success=success, latency_ms=latency_ms,
            error=error, args_summary=args_summary or None, caller=caller,
            result_summary=result_summary)
    except Exception:
        pass
    try:
        event: dict[str, Any] = {"brick": brick_name, "tool": tool_name,
            "success": success, "latency_ms": latency_ms, "ts": time.time()}
        for key, value in (("args_summary", args_summary), ("caller", caller),
                           ("session_id", session_id), ("workflow_run_id", workflow_run_id),
                           ("result_summary", result_summary)):
            if value:
                event[key] = value
        if error:
            event["error_type"] = error
        event_bus.publish(event)
    except Exception:
        pass
