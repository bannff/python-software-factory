"""Tests for OTel SDK-native storage exporters."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from opentelemetry.sdk.trace.export import SpanExportResult
from opentelemetry.sdk.metrics.export import MetricExportResult
from opentelemetry.sdk._logs.export import LogExportResult

from factory.telemetry.runtime.adapters.storage import (
    StorageSpanExporter,
    StorageMetricExporter,
    StorageLogExporter,
    _get_store,
    _persist,
)

IFACE = "factory.storage.interface"


@pytest.fixture
def mock_runtime():
    """Patch the public storage runtime accessor and return its runtime."""
    rt = MagicMock()
    with patch(f"{IFACE}.get_runtime", return_value=rt):
        yield rt


@pytest.fixture
def mock_store(mock_runtime):
    """Return a MagicMock store wired to the patched runtime (document)."""
    store = MagicMock()
    mock_runtime.get_document_store.return_value = store
    return store


class TestGetStore:
    """Tests for _get_store helper."""

    def test_returns_document_store(self, mock_runtime, monkeypatch):
        monkeypatch.setenv("TELEMETRY_SQLITE_PATH", "/tmp/test-telemetry.db")
        store = _get_store("document")
        mock_runtime.get_document_store.assert_called_once_with(
            "sqlite", db_path="/tmp/test-telemetry.db",
        )
        assert store is mock_runtime.get_document_store.return_value

    def test_returns_blob_store(self, mock_runtime):
        store = _get_store("blob")
        mock_runtime.get_blob_store.assert_called_once()
        assert store is mock_runtime.get_blob_store.return_value

    def test_returns_graph_store(self, mock_runtime):
        store = _get_store("graph")
        mock_runtime.get_graph_store.assert_called_once()
        assert store is mock_runtime.get_graph_store.return_value

    def test_raises_on_unknown_type(self, mock_runtime):
        with pytest.raises(ValueError, match="Unknown storage_type"):
            _get_store("redis")


class TestPersist:
    """Tests for _persist helper."""

    def test_document_calls_insert(self):
        store = MagicMock()
        _persist(store, "document", "col", '{"a":1}')
        store.insert.assert_called_once_with("col", {"otel_json": '{"a":1}'})

    def test_blob_calls_put_with_json_content_type_and_collection_key(self):
        store = MagicMock()
        _persist(store, "blob", "my_col", '{"a":1}')
        store.put.assert_called_once()
        args, kwargs = store.put.call_args
        assert args[0].startswith("my_col/")
        assert kwargs["content_type"] == "application/json"

    def test_blob_encodes_data_as_utf8(self):
        store = MagicMock()
        _persist(store, "blob", "c", "héllo")
        raw = store.put.call_args[0][1]
        assert raw == "héllo".encode("utf-8")

    def test_graph_calls_add_node_kwargs_only(self):
        store = MagicMock()
        _persist(store, "graph", "spans", '{"k":"v"}')
        store.add_node.assert_called_once_with(
            labels=["Telemetry", "spans"], properties={"k": "v"},
        )
        assert store.add_node.call_args[0] == ()  # no positional node_id


class TestStorageSpanExporter:
    """Tests for StorageSpanExporter."""

    @pytest.fixture
    def exporter(self, mock_store):
        exp = StorageSpanExporter(storage_type="document")
        exp._store = mock_store
        return exp

    def test_lazy_store_init(self):
        exp = StorageSpanExporter()
        assert exp._store is None

    def test_export_success(self, exporter, mock_store):
        span = MagicMock()
        span.to_json.return_value = '{"name":"op"}'
        assert exporter.export([span]) == SpanExportResult.SUCCESS

    def test_export_calls_persist_per_span(self, exporter, mock_store):
        spans = [MagicMock(), MagicMock()]
        for s in spans:
            s.to_json.return_value = "{}"
        exporter.export(spans)
        assert mock_store.insert.call_count == 2

    def test_export_returns_failure_on_exception(self, exporter, mock_store):
        mock_store.insert.side_effect = RuntimeError("boom")
        span = MagicMock(); span.to_json.return_value = "{}"
        assert exporter.export([span]) == SpanExportResult.FAILURE

    def test_shutdown_noop(self, exporter):
        exporter.shutdown()  # must not raise

    def test_force_flush_returns_true(self, exporter):
        assert exporter.force_flush() is True


class TestStorageMetricExporter:
    """Tests for StorageMetricExporter."""

    @pytest.fixture
    def exporter(self, mock_store):
        exp = StorageMetricExporter(storage_type="document")
        exp._store = mock_store
        return exp

    def test_super_init_called(self):
        """MetricExporter.__init__ must be called for _preferred_temporality."""
        exp = StorageMetricExporter()
        assert hasattr(exp, "_preferred_temporality")

    def test_export_success(self, exporter, mock_store):
        md = MagicMock(); md.to_json.return_value = '{"m":1}'
        assert exporter.export(md) == MetricExportResult.SUCCESS

    def test_export_returns_failure_on_exception(self, exporter, mock_store):
        mock_store.insert.side_effect = Exception("fail")
        md = MagicMock(); md.to_json.return_value = "{}"
        assert exporter.export(md) == MetricExportResult.FAILURE

    def test_shutdown_noop(self, exporter):
        exporter.shutdown()

    def test_force_flush_returns_true(self, exporter):
        assert exporter.force_flush() is True


class TestStorageLogExporter:
    """Tests for StorageLogExporter."""

    @pytest.fixture
    def exporter(self, mock_store):
        exp = StorageLogExporter(storage_type="document")
        exp._store = mock_store
        return exp

    def test_export_success(self, exporter, mock_store):
        rec = MagicMock(); rec.to_json.return_value = '{"body":"hi"}'
        assert exporter.export([rec]) == LogExportResult.SUCCESS

    def test_export_calls_persist_per_record(self, exporter, mock_store):
        recs = [MagicMock(), MagicMock(), MagicMock()]
        for r in recs:
            r.to_json.return_value = "{}"
        exporter.export(recs)
        assert mock_store.insert.call_count == 3

    def test_export_returns_failure_on_exception(self, exporter, mock_store):
        mock_store.insert.side_effect = ValueError("bad")
        rec = MagicMock(); rec.to_json.return_value = "{}"
        assert exporter.export([rec]) == LogExportResult.FAILURE

    def test_shutdown_noop(self, exporter):
        exporter.shutdown()

    def test_empty_batch_succeeds(self, exporter):
        assert exporter.export([]) == LogExportResult.SUCCESS

    def test_force_flush_returns_true(self, exporter):
        assert exporter.force_flush() is True
