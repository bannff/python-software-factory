from __future__ import annotations

from factory.telemetry.runtime.config import ExporterConfig, Settings
from factory.telemetry.runtime.otel_setup import configure_otel


def test_configure_otel_attaches_every_tracing_exporter() -> None:
    settings = Settings.model_validate({
        "service": {"name": "multi-exporter-test"},
        "otel": {
            "enabled": True, "tracing_enabled": True,
            "metrics_enabled": False, "logging_enabled": False,
        },
    })
    exporters = (
        ExporterConfig(id="first", kind="console"),
        ExporterConfig(id="second", kind="console"),
    )
    runtime = configure_otel(settings, exporters)
    try:
        assert isinstance(runtime.span_exporter, tuple)
        assert len(runtime.span_exporter) == 2
        processors = runtime.tracer_provider._active_span_processor._span_processors
        assert len(processors) == 2
    finally:
        runtime.tracer_provider.shutdown()
        runtime.meter_provider.shutdown()
