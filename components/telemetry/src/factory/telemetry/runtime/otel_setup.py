from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from opentelemetry import metrics, trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk._logs import LoggerProvider
from opentelemetry._logs import set_logger_provider

from factory.telemetry.runtime.config import ExporterConfig, Settings, normalize_otlp_http_endpoint


@dataclass(frozen=True)
class OTelRuntime:
    tracer_provider: TracerProvider
    meter_provider: MeterProvider
    logger_provider: LoggerProvider | None
    span_exporter: Any | None = None


def configure_otel(
    settings: Settings,
    exporter: ExporterConfig | tuple[ExporterConfig, ...] | None,
    provenance: Any = None,
) -> OTelRuntime:
    exporters = (
        () if exporter is None else
        (exporter,) if isinstance(exporter, ExporterConfig) else exporter
    )
    resource = Resource.create(
        {
            "service.name": settings.service.name,
            **({"service.version": settings.service.version} if settings.service.version else {}),
        }
    )

    tracer_provider = TracerProvider(resource=resource)

    # Tracing exporters
    span_exporters: list[Any] = []
    if settings.otel.enabled and settings.otel.tracing_enabled:
        for config in exporters:
            span_exporters.append(_configure_tracing_exporter(
                tracer_provider, config, provenance,
            ))

    trace.set_tracer_provider(tracer_provider)

    # Metrics exporters
    metric_readers = []
    if settings.otel.enabled and settings.otel.metrics_enabled:
        for config in exporters:
            if config.kind == "provenance":
                continue
            reader = _build_metric_reader(config)
            if reader:
                metric_readers.append(reader)

    meter_provider = MeterProvider(resource=resource, metric_readers=metric_readers)
    metrics.set_meter_provider(meter_provider)

    # Logging exporters
    logger_provider: LoggerProvider | None = None
    logging_exporters = tuple(
        config for config in exporters if config.kind != "provenance"
    )
    if settings.otel.enabled and settings.otel.logging_enabled and logging_exporters:
        from .otel_logging import configure_logging_exporters
        logger_provider = configure_logging_exporters(resource, logging_exporters)
        set_logger_provider(logger_provider)

    span_exporter: Any | None = None
    if len(span_exporters) == 1:
        span_exporter = span_exporters[0]
    elif span_exporters:
        span_exporter = tuple(span_exporters)
    return OTelRuntime(
        tracer_provider=tracer_provider,
        meter_provider=meter_provider,
        logger_provider=logger_provider,
        span_exporter=span_exporter,
    )


def _configure_tracing_exporter(
    tracer_provider: TracerProvider, exporter: ExporterConfig, provenance: Any,
) -> Any:
    if exporter.kind == "provenance":
        if provenance is None or exporter.context is None:
            raise ValueError("provenance exporter requires runtime and context")
        from .provenance_exporter import ProvenanceSpanExporter
        span_exporter = ProvenanceSpanExporter(
            provenance,
            context=exporter.context,
            mappings=exporter.mappings,
            activation=exporter.activation,
        )
    elif exporter.kind == "console":
        from opentelemetry.sdk.trace.export import ConsoleSpanExporter
        span_exporter = ConsoleSpanExporter()
    elif exporter.kind == "storage":
        from factory.telemetry.runtime.adapters.storage import StorageSpanExporter
        span_exporter = StorageSpanExporter(exporter.storage_type)
    elif exporter.protocol == "http/protobuf":
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
            OTLPSpanExporter as HttpOTLPSpanExporter,
        )

        endpoint = normalize_otlp_http_endpoint(exporter.endpoint, "traces")
        span_exporter: Any = HttpOTLPSpanExporter(
            endpoint=endpoint,
            headers=exporter.headers,
            timeout=exporter.timeout_seconds,
        )
    else:
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
            OTLPSpanExporter as GrpcOTLPSpanExporter,
        )

        span_exporter = GrpcOTLPSpanExporter(
            endpoint=exporter.endpoint,
            headers=exporter.headers,
            timeout=exporter.timeout_seconds,
        )

    span_processor: Any = BatchSpanProcessor(span_exporter)
    if exporter.kind == "provenance":
        from .suppression_processor import SuppressionAwareSpanProcessor
        span_processor = SuppressionAwareSpanProcessor(span_processor)
    tracer_provider.add_span_processor(span_processor)
    return span_exporter


def _build_metric_reader(exporter: ExporterConfig) -> PeriodicExportingMetricReader | None:
    if exporter.kind == "console":
        from opentelemetry.sdk.metrics.export import ConsoleMetricExporter
        return PeriodicExportingMetricReader(ConsoleMetricExporter())

    if exporter.kind == "storage":
        from factory.telemetry.runtime.adapters.storage import StorageMetricExporter
        return PeriodicExportingMetricReader(StorageMetricExporter(exporter.storage_type))

    if exporter.protocol == "http/protobuf":
        from opentelemetry.exporter.otlp.proto.http.metric_exporter import (
            OTLPMetricExporter as HttpOTLPMetricExporter,
        )

        endpoint = normalize_otlp_http_endpoint(exporter.endpoint, "metrics")
        metric_exporter: Any = HttpOTLPMetricExporter(
            endpoint=endpoint,
            headers=exporter.headers,
            timeout=exporter.timeout_seconds,
        )
    else:
        from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import (
            OTLPMetricExporter as GrpcOTLPMetricExporter,
        )

        metric_exporter = GrpcOTLPMetricExporter(
            endpoint=exporter.endpoint,
            headers=exporter.headers,
            timeout=exporter.timeout_seconds,
        )

    return PeriodicExportingMetricReader(metric_exporter)
