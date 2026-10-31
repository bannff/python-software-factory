"""OpenTelemetry logging exporter composition."""
from __future__ import annotations

from typing import Any

from opentelemetry.sdk._logs import LoggerProvider
from opentelemetry.sdk._logs.export import (
    BatchLogRecordProcessor, SimpleLogRecordProcessor,
)
from opentelemetry.sdk.resources import Resource

from .config import ExporterConfig, normalize_otlp_http_endpoint


def configure_logging_exporters(
    resource: Resource, exporters: tuple[ExporterConfig, ...],
) -> LoggerProvider:
    provider = LoggerProvider(resource=resource)
    for config in exporters:
        processor = _processor(config)
        if processor is not None:
            provider.add_log_record_processor(processor)
    return provider


def _processor(config: ExporterConfig) -> Any | None:
    if config.kind == "provenance":
        return None
    if config.kind == "console":
        from opentelemetry.sdk._logs.export import ConsoleLogExporter
        return SimpleLogRecordProcessor(ConsoleLogExporter())
    if config.kind == "storage":
        from factory.telemetry.runtime.adapters.storage import StorageLogExporter
        return SimpleLogRecordProcessor(StorageLogExporter(config.storage_type))
    if config.protocol == "http/protobuf":
        from opentelemetry.exporter.otlp.proto.http._log_exporter import (
            OTLPLogExporter as HttpOTLPLogExporter,
        )
        exporter: Any = HttpOTLPLogExporter(
            endpoint=normalize_otlp_http_endpoint(config.endpoint, "logs"),
            headers=config.headers, timeout=config.timeout_seconds,
        )
    else:
        from opentelemetry.exporter.otlp.proto.grpc._log_exporter import (
            OTLPLogExporter as GrpcOTLPLogExporter,
        )
        exporter = GrpcOTLPLogExporter(
            endpoint=config.endpoint, headers=config.headers,
            timeout=config.timeout_seconds,
        )
    return BatchLogRecordProcessor(exporter)


__all__ = ["configure_logging_exporters"]
