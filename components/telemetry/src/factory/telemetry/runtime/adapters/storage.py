"""OTel SDK-native exporters that persist to the storage brick.

Implements the SDK's SpanExporter, MetricExporter, and LogExporter
ABCs so telemetry flows through the standard OTel pipeline into
whatever storage backend is configured (document, blob, graph).

Uses factory.storage.interface (canonical cross-brick import).
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any, Literal, Sequence

from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult
from opentelemetry.sdk.metrics.export import (
    MetricExporter,
    MetricExportResult,
    MetricsData,
)
from opentelemetry.sdk._logs.export import LogExporter, LogExportResult

logger = logging.getLogger(__name__)

StorageType = Literal["document", "blob", "graph"]

COLLECTION_SPANS = "telemetry_spans"
COLLECTION_METRICS = "telemetry_metrics"
COLLECTION_LOGS = "telemetry_logs"


def _get_store(storage_type: StorageType) -> Any:
    """Lazy-load the appropriate store from storage brick."""
    from factory.storage.interface import get_runtime

    rt = get_runtime()
    if storage_type == "document":
        import os
        path = os.getenv("TELEMETRY_SQLITE_PATH", "./.storage/telemetry.db")
        return rt.get_document_store("sqlite", db_path=path)
    elif storage_type == "blob":
        return rt.get_blob_store()
    elif storage_type == "graph":
        return rt.get_graph_store()
    raise ValueError(f"Unknown storage_type: {storage_type}")


def _persist(store: Any, storage_type: StorageType, collection: str, data: str) -> None:
    """Persist JSON data to the configured store type."""
    if storage_type == "document":
        store.insert(collection, {"otel_json": data})
    elif storage_type == "blob":
        key = f"{collection}/{uuid.uuid4().hex}"
        store.put(key, data.encode("utf-8"), content_type="application/json")
    elif storage_type == "graph":
        parsed = json.loads(data)
        store.add_node(labels=["Telemetry", collection], properties=parsed)


class StorageSpanExporter(SpanExporter):
    """OTel SpanExporter that persists spans via storage brick."""

    def __init__(self, storage_type: StorageType = "document") -> None:
        self._storage_type = storage_type
        self._store: Any = None

    @property
    def store(self) -> Any:
        if self._store is None:
            self._store = _get_store(self._storage_type)
        return self._store

    def export(self, spans: Sequence[Any]) -> SpanExportResult:
        try:
            for span in spans:
                _persist(self.store, self._storage_type, COLLECTION_SPANS, span.to_json())
            return SpanExportResult.SUCCESS
        except Exception:
            logger.exception("Failed to export spans to storage")
            return SpanExportResult.FAILURE

    def shutdown(self) -> None:
        pass

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        return True


class StorageMetricExporter(MetricExporter):
    """OTel MetricExporter that persists metrics via storage brick."""

    def __init__(self, storage_type: StorageType = "document") -> None:
        super().__init__()
        self._storage_type = storage_type
        self._store: Any = None

    @property
    def store(self) -> Any:
        if self._store is None:
            self._store = _get_store(self._storage_type)
        return self._store

    def export(
        self, metrics_data: MetricsData, timeout_millis: float = 10000, **kwargs: Any,
    ) -> MetricExportResult:
        try:
            _persist(
                self.store, self._storage_type, COLLECTION_METRICS, metrics_data.to_json(),
            )
            return MetricExportResult.SUCCESS
        except Exception:
            logger.exception("Failed to export metrics to storage")
            return MetricExportResult.FAILURE

    def shutdown(self, timeout_millis: float = 30000, **kwargs: Any) -> None:
        pass

    def force_flush(self, timeout_millis: float = 10000) -> bool:
        return True


class StorageLogExporter(LogExporter):
    """OTel LogExporter that persists logs via storage brick."""

    def __init__(self, storage_type: StorageType = "document") -> None:
        self._storage_type = storage_type
        self._store: Any = None

    @property
    def store(self) -> Any:
        if self._store is None:
            self._store = _get_store(self._storage_type)
        return self._store

    def export(self, batch: Sequence[Any]) -> LogExportResult:
        try:
            for record in batch:
                _persist(self.store, self._storage_type, COLLECTION_LOGS, record.to_json())
            return LogExportResult.SUCCESS
        except Exception:
            logger.exception("Failed to export logs to storage")
            return LogExportResult.FAILURE

    def shutdown(self) -> None:
        pass

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        return True
