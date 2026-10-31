"""Tests for OTLP exporter configuration."""
from __future__ import annotations

import pytest

from factory.telemetry.runtime.config import (
    ExporterConfig,
    normalize_otlp_http_endpoint,
    filter_attributes,
)


class TestNormalizeOtlpEndpoint:
    """Test OTLP endpoint normalization."""

    def test_adds_traces_path(self) -> None:
        """Should add /v1/traces to base URL."""
        result = normalize_otlp_http_endpoint("http://localhost:4318", "traces")
        assert result == "http://localhost:4318/v1/traces"

    def test_adds_metrics_path(self) -> None:
        """Should add /v1/metrics to base URL."""
        result = normalize_otlp_http_endpoint("http://localhost:4318", "metrics")
        assert result == "http://localhost:4318/v1/metrics"

    def test_preserves_existing_path(self) -> None:
        """Should not double-add path if already present."""
        result = normalize_otlp_http_endpoint("http://localhost:4318/v1/traces", "traces")
        assert result == "http://localhost:4318/v1/traces"

    def test_strips_trailing_slash(self) -> None:
        """Should handle trailing slash."""
        result = normalize_otlp_http_endpoint("http://localhost:4318/", "traces")
        assert result == "http://localhost:4318/v1/traces"


class TestExporterConfig:
    """Test exporter configuration model."""

    def test_http_protobuf_default(self) -> None:
        """Default protocol should be http/protobuf."""
        cfg = ExporterConfig(kind="otlp", endpoint="http://localhost:4318")
        assert cfg.protocol == "http/protobuf"

    def test_grpc_protocol(self) -> None:
        """Should accept grpc protocol."""
        cfg = ExporterConfig(kind="otlp", endpoint="localhost:4317", protocol="grpc")
        assert cfg.protocol == "grpc"

    def test_default_timeout(self) -> None:
        """Default timeout should be 10 seconds."""
        cfg = ExporterConfig(kind="otlp", endpoint="http://localhost:4318")
        assert cfg.timeout_seconds == 10

    def test_custom_headers(self) -> None:
        """Should accept custom headers."""
        cfg = ExporterConfig(
            kind="otlp",
            endpoint="http://localhost:4318",
            headers={"Authorization": "Bearer token"},
        )
        assert cfg.headers["Authorization"] == "Bearer token"


class TestFilterAttributes:
    """Test attribute filtering."""

    def test_filters_to_allowed(self) -> None:
        """Should only keep allowed attributes."""
        result = filter_attributes(
            allowed=["a", "b"],
            attrs={"a": 1, "b": 2, "c": 3},
        )
        assert result == {"a": 1, "b": 2}

    def test_empty_allowed_returns_all(self) -> None:
        """Empty allowed list should return all attributes."""
        result = filter_attributes(
            allowed=[],
            attrs={"a": 1, "b": 2},
        )
        assert result == {"a": 1, "b": 2}

    def test_none_attrs_returns_empty(self) -> None:
        """None attrs should return empty dict."""
        result = filter_attributes(allowed=["a"], attrs=None)
        assert result == {}
