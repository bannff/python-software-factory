"""Default OpenTelemetry env injected into every provisioned sandbox.

So any process an agent runs inside a container (build, test, or a deployed
agent squad) can export traces/metrics/logs back to the parent Companion-X
OTLP collector and light up the UI — without per-profile boilerplate.

Enabled by default; opt out with SANDBOX_OTEL_ENABLED=0. The endpoint is
taken from SANDBOX_OTEL_ENDPOINT (falls back to the standard
OTEL_EXPORTER_OTLP_ENDPOINT if already set in the server env).
"""
from __future__ import annotations

import os


def _truthy(value: str | None, *, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def default_otel_env(env_id: str, profile_name: str | None = None) -> dict[str, str]:
    """Build the default OTEL env for a provisioned container.

    Returns ``{}`` when disabled or when no collector endpoint is configured
    (injecting a half-set OTEL config would just produce export errors).
    """
    if not _truthy(os.environ.get("SANDBOX_OTEL_ENABLED"), default=True):
        return {}
    endpoint = (
        os.environ.get("SANDBOX_OTEL_ENDPOINT")
        or os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
    )
    if not endpoint:
        return {}

    service = f"sandbox-{profile_name}" if profile_name else "sandbox"
    resource_attrs = (
        f"service.name={service},"
        f"sandbox.env_id={env_id},"
        f"sandbox.profile={profile_name or 'ad_hoc'}"
    )
    env = {
        "OTEL_EXPORTER_OTLP_ENDPOINT": endpoint,
        "OTEL_SERVICE_NAME": service,
        "OTEL_RESOURCE_ATTRIBUTES": resource_attrs,
        "OTEL_TRACES_EXPORTER": "otlp",
        "OTEL_METRICS_EXPORTER": "otlp",
        "OTEL_LOGS_EXPORTER": "otlp",
    }
    protocol = os.environ.get("SANDBOX_OTEL_PROTOCOL")
    if protocol:
        env["OTEL_EXPORTER_OTLP_PROTOCOL"] = protocol
    return env
