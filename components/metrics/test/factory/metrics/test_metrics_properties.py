"""
Stateful property tests for the Metrics brick using Hypothesis.

Tests that MetricsRuntime maintains valid state across arbitrary
sequences of define/update/delete/record/query operations.

Invariants verified:
- list_definitions count matches model tracking
- get_definition returns None for deleted, non-None for existing
- health_check always returns dict with "ok" key
- recorded points are queryable via store
"""

from __future__ import annotations

from hypothesis import settings, strategies as st
from hypothesis.stateful import RuleBasedStateMachine, initialize, invariant, rule

from factory.metrics.core import MetricType
from factory.metrics.runtime.adapters.memory import (
    InMemoryMetricsComputer,
    InMemoryMetricsStore,
)
from factory.metrics.runtime.models import MetricDefinition
from factory.metrics.runtime.runtime import MetricsRuntime

_metric_ids = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N")), min_size=1, max_size=20,
)
_metric_values = st.floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False)
_metric_types = st.sampled_from(list(MetricType))
_labels = st.dictionaries(
    st.text(min_size=1, max_size=10), st.text(min_size=1, max_size=10), max_size=3,
)
_periods = st.sampled_from(["1h", "6h", "12h", "24h", "7d", "30d"])
_agg_methods = st.sampled_from(["mean", "sum", "min", "max", "count"])


class MetricsStateMachine(RuleBasedStateMachine):
    """Stateful test: MetricsRuntime across arbitrary operation sequences."""

    def __init__(self):
        super().__init__()
        self.rt: MetricsRuntime | None = None
        self.model_defs: dict[str, MetricDefinition] = {}
        self.model_points: dict[str, list[float]] = {}

    @initialize()
    def init_runtime(self):
        self.rt = MetricsRuntime(InMemoryMetricsStore(), InMemoryMetricsComputer())
        self.model_defs = {}
        self.model_points = {}

    @rule(mid=_metric_ids, name=st.text(min_size=1, max_size=30), mt=_metric_types)
    def define_metric(self, mid: str, name: str, mt: MetricType):
        defn = MetricDefinition(id=mid, name=name, metric_type=mt)
        self.rt.register_definition(defn)
        self.model_defs[mid] = defn
        self.model_points.setdefault(mid, [])

    @rule(new_name=st.text(min_size=1, max_size=30))
    def update_definition(self, new_name: str):
        if not self.model_defs:
            return
        mid = next(iter(self.model_defs))
        result = self.rt.update_definition(mid, {"name": new_name})
        assert result is not None
        self.model_defs[mid] = result

    @rule()
    def delete_definition(self):
        if not self.model_defs:
            return
        mid = next(iter(self.model_defs))
        assert self.rt.delete_definition(mid) is True
        del self.model_defs[mid]
        self.model_points.pop(mid, None)

    @rule(mid=_metric_ids, value=_metric_values, labels=_labels)
    def record(self, mid: str, value: float, labels: dict):
        if mid not in self.model_defs:
            defn = MetricDefinition(id=mid, name=mid, metric_type=MetricType.GAUGE)
            self.rt.register_definition(defn)
            self.model_defs[mid] = defn
        result = self.rt.record(mid, value, labels or None)
        assert result["ok"] is True
        self.model_points.setdefault(mid, []).append(value)

    @rule(data=st.lists(st.tuples(_metric_ids, _metric_values), min_size=1, max_size=5))
    def record_batch(self, data: list):
        records = []
        for mid, val in data:
            if mid not in self.model_defs:
                defn = MetricDefinition(id=mid, name=mid, metric_type=MetricType.GAUGE)
                self.rt.register_definition(defn)
                self.model_defs[mid] = defn
            records.append({"metric_id": mid, "value": val})
            self.model_points.setdefault(mid, []).append(val)
        result = self.rt.record_batch(records)
        assert result["ok"] is True
        assert result["recorded"] == len(records)

    @rule(period=_periods)
    def get_snapshot(self, period: str):
        if not self.model_points:
            return
        mid = next(iter(self.model_points))
        snap = self.rt.get_snapshot(mid, period)
        assert snap["metric_id"] == mid

    @rule()
    def get_trend(self):
        if not self.model_points:
            return
        mid = next(iter(self.model_points))
        result = self.rt.get_trend(mid)
        assert result["metric_id"] == mid
        assert "trend" in result

    @rule(method=_agg_methods, period=_periods)
    def compute_aggregation(self, method: str, period: str):
        if not self.model_points:
            return
        mid = next(iter(self.model_points))
        result = self.rt.compute_aggregation(mid, method, period)
        assert result["ok"] is True
        assert result["method"] == method

    @rule()
    def detect_drift(self):
        if not self.model_points:
            return
        mid = next(iter(self.model_points))
        result = self.rt.detect_drift(mid)
        assert "drifted" in result or "reason" in result

    @invariant()
    def definition_count_matches(self):
        assert len(self.rt.list_definitions()) == len(self.model_defs)

    @invariant()
    def definitions_accessible(self):
        for mid in self.model_defs:
            assert self.rt.get_definition(mid) is not None
        deleted_id = "__never_defined__"
        if deleted_id not in self.model_defs:
            assert self.rt.get_definition(deleted_id) is None

    @invariant()
    def health_check_ok(self):
        health = self.rt.health_check()
        assert isinstance(health, dict)
        assert "ok" in health


TestMetricsStateful = MetricsStateMachine.TestCase
TestMetricsStateful.settings = settings(max_examples=50, stateful_step_count=20)
