"""Tests for strict W3C context propagation."""
from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from factory.telemetry.runtime.runtime import TelemetryRuntime
from factory.telemetry.runtime.trace_context import TraceContextModel


def _create_runtime(tmp_path: Path) -> TelemetryRuntime:
    cfg = tmp_path / "config"
    (cfg / "metrics").mkdir(parents=True)
    (cfg / "exporters").mkdir(parents=True)
    (cfg / "settings.yaml").write_text(
        """
service:
  name: test-service
otel:
  enabled: true
  tracing_enabled: true
  metrics_enabled: false
  logging_enabled: false
""".lstrip()
    )
    runtime = TelemetryRuntime(config_dir=cfg)
    runtime.initialize()
    return runtime


class TestContextPropagation:
    def test_inject_without_active_context_is_explicit(self, tmp_path: Path) -> None:
        result = _create_runtime(tmp_path).inject_context()
        assert result["ok"] is False
        assert result["outcome"] == "no_context"
        assert result["error"] == "no_active_trace_context"

    def test_valid_round_trip_preserves_tracestate(self, tmp_path: Path) -> None:
        runtime = _create_runtime(tmp_path)
        carrier = {
            "traceparent": "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01",
            "tracestate": "vendor=value,other=state",
        }
        result = runtime.extract_context(carrier)
        assert result["ok"] is True
        assert result["outcome"] == "extracted"
        assert result["trace_id"] == "0af7651916cd43dd8448eb211c80319c"
        assert result["span_id"] == "b7ad6b7169203331"
        assert result["traceparent"] == carrier["traceparent"]
        assert result["traceparent_version"] == "00"
        assert result["carrier"] == carrier
        assert result["tracestate"] == carrier["tracestate"]

    def test_malformed_traceparent_is_rejected(self, tmp_path: Path) -> None:
        result = _create_runtime(tmp_path).extract_context({"traceparent": "invalid"})
        assert result["ok"] is False
        assert result["outcome"] == "rejected"
        assert result["error"] == "malformed traceparent"

    @pytest.mark.parametrize(
        "traceparent",
        [
            "00-00000000000000000000000000000000-b7ad6b7169203331-01",
            "00-0af7651916cd43dd8448eb211c80319c-0000000000000000-01",
        ],
    )
    def test_all_zero_w3c_ids_are_rejected(self, tmp_path: Path, traceparent: str) -> None:
        result = _create_runtime(tmp_path).extract_context({"traceparent": traceparent})
        assert result["ok"] is False
        assert result["outcome"] == "rejected"
        assert "all zero" in result["error"]

    def test_malformed_tracestate_is_rejected(self, tmp_path: Path) -> None:
        result = _create_runtime(tmp_path).extract_context({
            "traceparent": "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01",
            "tracestate": "not-a-member",
        })
        assert result["ok"] is False
        assert result["outcome"] == "rejected"
        assert result["error"] == "malformed tracestate"

    def test_duplicate_tracestate_members_are_rejected(self, tmp_path: Path) -> None:
        result = _create_runtime(tmp_path).extract_context({
            "traceparent": "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01",
            "tracestate": "vendor=value,vendor=other",
        })
        assert result["ok"] is False
        assert result["outcome"] == "rejected"
        assert result["error"] == "malformed tracestate"


class TestFlushTelemetry:
    def test_flush_returns_success(self, tmp_path: Path) -> None:
        result = _create_runtime(tmp_path).flush_telemetry(timeout_ms=1000)
        assert result["ok"] is True
        assert "flushed" in result


def test_unsupported_traceparent_version_is_rejected(tmp_path: Path) -> None:
    result = _create_runtime(tmp_path).extract_context({
        "traceparent": "01-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01",
    })
    assert result["ok"] is False
    assert result["outcome"] == "rejected"
    assert result["error"] == "unsupported traceparent version: 01"


def test_duplicate_traceparent_headers_are_rejected(tmp_path: Path) -> None:
    result = _create_runtime(tmp_path).extract_context({
        "traceparent": "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01",
        "Traceparent": "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01",
    })
    assert result["ok"] is False
    assert result["outcome"] == "rejected"
    assert result["error"] == "duplicate W3C context"


def _valid_model_values() -> dict[str, object]:
    return {
        "traceparent": "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01",
        "traceparent_version": "00",
        "trace_id": "0af7651916cd43dd8448eb211c80319c",
        "span_id": "b7ad6b7169203331",
        "trace_flags": 1,
        "tracestate": "vendor=value",
        "carrier": {
            "traceparent": "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01",
            "tracestate": "vendor=value",
        },
    }


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (
            {"traceparent": "01-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01"},
            "unsupported traceparent version",
        ),
        ({"trace_id": "1234567890abcdef1234567890abcdef"}, "trace_id does not match"),
        ({"tracestate": "broken"}, "malformed tracestate"),
        (
            {"carrier": {"traceparent": "00-1234567890abcdef1234567890abcdef-b7ad6b7169203331-01"}},
            "carrier traceparent does not match",
        ),
    ],
)
def test_direct_trace_context_rejects_inconsistent_values(
    change: dict[str, object], message: str,
) -> None:
    values = _valid_model_values()
    values.update(change)
    with pytest.raises(ValidationError, match=message):
        TraceContextModel(**values)
