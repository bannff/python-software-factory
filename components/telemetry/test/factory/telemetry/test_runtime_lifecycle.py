"""Fail-closed Telemetry initialization, health, and flush behavior."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from factory.telemetry.runtime import lifecycle
from factory.telemetry.runtime.runtime import TelemetryRuntime


def _write_config(root: Path, *, exporter: str | None = None) -> Path:
    config = root / "telemetry"
    (config / "exporters").mkdir(parents=True)
    (config / "settings.yaml").write_text(
        "service:\n  name: lifecycle-test\n"
        "otel:\n  enabled: true\n  tracing_enabled: true\n"
        "  metrics_enabled: false\n  logging_enabled: false\n"
    )
    if exporter is not None:
        (config / "exporters" / "exporter.yaml").write_text(exporter)
    return config


def test_failed_initialize_is_atomic_and_unhealthy(tmp_path: Path) -> None:
    config = _write_config(tmp_path, exporter="id: broken\nkind: provenance\n")
    runtime = TelemetryRuntime(config)

    with pytest.raises(ValueError, match="requires runtime and context"):
        runtime.initialize()

    assert runtime.settings is None
    assert runtime.settings_raw is None
    assert runtime.otel is None
    assert runtime.registries.exporters.exporters == {}
    health = runtime.health_check()
    assert health["ok"] is False
    assert "ValueError" in health["error"]


def test_required_server_propagates_malformed_config(
    tmp_path: Path, monkeypatch,
) -> None:
    from factory.telemetry import server

    config = _write_config(tmp_path, exporter="id: broken\nkind: provenance\n")
    monkeypatch.setattr(server, "_RUNTIME", None)
    monkeypatch.setenv("TELEMETRY_CONFIG_DIR", str(config))
    monkeypatch.setenv("TELEMETRY_REQUIRED", "1")

    with pytest.raises(ValueError, match="requires runtime and context"):
        server.get_runtime()
    assert server._RUNTIME is None


def test_enabled_tracing_without_exporter_is_unhealthy(tmp_path: Path) -> None:
    runtime = TelemetryRuntime(_write_config(tmp_path))
    runtime.initialize()

    assert runtime.health_check() == {
        "ok": False,
        "error": "tracing_enabled_but_exporter_missing",
        "service": {"name": "lifecycle-test", "version": None},
        "otel": {
            "enabled": True,
            "tracing_enabled": True,
            "metrics_enabled": False,
            "logging_enabled": False,
        },
        "exporters": [],
        "span_exporter": None,
    }


def test_flush_reports_provider_timeout() -> None:
    provider = SimpleNamespace(force_flush=lambda **_kwargs: False)
    runtime = SimpleNamespace(otel=SimpleNamespace(
        tracer_provider=provider,
        meter_provider=SimpleNamespace(force_flush=lambda **_kwargs: True),
        logger_provider=None,
    ))

    result = lifecycle.flush(runtime, 10)

    assert result == {
        "ok": False,
        "flushed": ["metrics"],
        "error": "traces: timeout",
    }
