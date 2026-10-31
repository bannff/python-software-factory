"""Basic smoke tests for the metrics brick."""

from factory.metrics.core import MetricType, DataPoint, parse_duration
from factory.metrics.runtime.models import MetricDefinition, Snapshot
from factory.metrics.runtime.adapters.memory import (
    InMemoryMetricsStore,
    InMemoryMetricsComputer,
)
from factory.metrics.runtime.runtime import MetricsRuntime


def _make_runtime() -> MetricsRuntime:
    return MetricsRuntime(
        store=InMemoryMetricsStore(),
        computer=InMemoryMetricsComputer(),
    )


def test_metric_type_enum():
    assert MetricType.COUNTER.value == "counter"
    assert MetricType.GAUGE.value == "gauge"


def test_parse_duration():
    assert parse_duration("24h") == 86400.0
    assert parse_duration("7d") == 604800.0
    assert parse_duration("30m") == 1800.0


def test_record_and_query():
    rt = _make_runtime()
    result = rt.record("test_metric", 42.0)
    assert result["ok"] is True
    assert result["metric_id"] == "test_metric"


def test_definition_crud():
    rt = _make_runtime()
    defn = MetricDefinition(
        id="cov", name="Coverage", description="Test coverage",
        metric_type=MetricType.GAUGE,
    )
    rt.register_definition(defn)
    assert rt.get_definition("cov") is not None
    assert len(rt.list_definitions()) == 1
    assert rt.delete_definition("cov") is True
    assert rt.get_definition("cov") is None


def test_capabilities():
    rt = _make_runtime()
    caps = rt.get_capabilities()
    assert caps["name"] == "metrics"
    assert "features" in caps


def test_health_check():
    rt = _make_runtime()
    health = rt.health_check()
    assert health["ok"] is True
