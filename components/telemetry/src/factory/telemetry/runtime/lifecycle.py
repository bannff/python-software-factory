"""Fail-closed health and flush helpers for the Telemetry runtime."""
from __future__ import annotations

from typing import Any


def health(runtime: Any) -> dict[str, Any]:
    """Report only fully initialized, usable tracing as healthy."""
    if runtime._initialization_error is not None:
        return {"ok": False, "error": runtime._initialization_error}
    if runtime.settings is None:
        return {"ok": False, "error": "runtime_not_initialized"}
    if runtime.otel is None:
        return {"ok": False, "error": "otel_not_initialized"}

    tracing_required = (
        runtime.settings.otel.enabled and runtime.settings.otel.tracing_enabled
    )
    exporter = runtime.otel.span_exporter
    exporter_health = _exporter_health(exporter)
    if tracing_required and exporter is None:
        error = "tracing_enabled_but_exporter_missing"
    elif tracing_required and not exporter_health.get("ok", False):
        error = str(exporter_health.get("error") or "span_exporter_unhealthy")
    else:
        error = None
    return {
        "ok": error is None,
        **({"error": error} if error else {}),
        "service": runtime.settings.service.model_dump(),
        "otel": runtime.settings.otel.model_dump(),
        "exporters": list(runtime.registries.exporters.exporters),
        "span_exporter": exporter_health if exporter is not None else None,
    }


def _exporter_health(exporter: Any) -> dict[str, Any]:
    if exporter is None:
        return {"ok": False, "error": "span_exporter_missing"}
    if isinstance(exporter, tuple):
        results = [_exporter_health(item) for item in exporter]
        errors = [str(item.get("error")) for item in results if not item.get("ok")]
        return {
            "ok": not errors, "exporters": results,
            **({"error": "; ".join(errors)} if errors else {}),
        }
    check = getattr(exporter, "health_check", None)
    if not callable(check):
        return {"ok": True}
    try:
        result = check()
    except Exception as exc:  # noqa: BLE001 - readiness must fail closed
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
    if isinstance(result, dict):
        return result
    return {"ok": bool(result)}


def flush(runtime: Any, timeout_ms: int) -> dict[str, Any]:
    """Flush each provider and retain SDK timeout/failure results."""
    if runtime.otel is None:
        return {"ok": False, "error": "otel_not_initialized"}
    providers = [
        ("traces", runtime.otel.tracer_provider),
        ("metrics", runtime.otel.meter_provider),
    ]
    if runtime.otel.logger_provider is not None:
        providers.append(("logs", runtime.otel.logger_provider))
    flushed: list[str] = []
    failures: list[str] = []
    for name, provider in providers:
        try:
            result = provider.force_flush(timeout_millis=timeout_ms)
            if result is False:
                failures.append(f"{name}: timeout")
            else:
                flushed.append(name)
        except Exception as exc:  # noqa: BLE001 - report every provider failure
            failures.append(f"{name}: {type(exc).__name__}: {exc}")
    return {
        "ok": not failures,
        "flushed": flushed,
        **({"error": "; ".join(failures)} if failures else {}),
    }
