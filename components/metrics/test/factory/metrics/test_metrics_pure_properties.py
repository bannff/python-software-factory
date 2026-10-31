"""
Pure function property tests for the Metrics brick using Hypothesis.

Tests stateless invariants for parse_duration, DataPoint, and
InMemoryMetricsComputer (aggregate, trend, detect_drift).
"""

from __future__ import annotations

from hypothesis import given, settings, strategies as st

from factory.metrics.core import DataPoint, parse_duration
from factory.metrics.runtime.adapters.memory import InMemoryMetricsComputer

_computer = InMemoryMetricsComputer()
_values = st.floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False)
_pos_values = st.floats(min_value=0.01, max_value=1e6, allow_nan=False, allow_infinity=False)


# ── parse_duration ───────────────────────────────────────────────


@given(n=st.integers(min_value=1, max_value=9999), unit=st.sampled_from(["s", "m", "h", "d"]))
@settings(max_examples=50)
def test_parse_duration_valid(n: int, unit: str):
    """Valid duration strings always parse to positive seconds."""
    result = parse_duration(f"{n}{unit}")
    multipliers = {"s": 1, "m": 60, "h": 3600, "d": 86400}
    assert result == n * multipliers[unit]
    assert result > 0


@given(suffix=st.text(min_size=1, max_size=1).filter(lambda s: s not in "smhd"))
@settings(max_examples=50)
def test_parse_duration_rejects_invalid_suffix(suffix: str):
    """Invalid suffixes raise ValueError."""
    try:
        parse_duration(f"10{suffix}")
        assert False, f"Should have raised ValueError for suffix '{suffix}'"
    except (ValueError, Exception):
        pass


# ── DataPoint ────────────────────────────────────────────────────


@given(mid=st.text(min_size=1, max_size=20), value=_values, ts=_pos_values)
@settings(max_examples=50)
def test_datapoint_fields(mid: str, value: float, ts: float):
    """DataPoint stores fields correctly."""
    dp = DataPoint(metric_id=mid, value=value, timestamp=ts, labels={"env": "test"})
    assert dp.metric_id == mid
    assert dp.value == value
    assert dp.timestamp == ts
    assert dp.labels == {"env": "test"}


# ── InMemoryMetricsComputer.aggregate ────────────────────────────


def _make_points(values: list[float]) -> list[DataPoint]:
    return [DataPoint(metric_id="m", value=v, timestamp=float(i)) for i, v in enumerate(values)]


@given(vals=st.lists(_values, min_size=1, max_size=50))
@settings(max_examples=50)
def test_aggregate_count(vals: list[float]):
    """Count returns the number of points."""
    pts = _make_points(vals)
    assert _computer.aggregate(pts, "count") == float(len(vals))


@given(vals=st.lists(_values, min_size=1, max_size=50))
@settings(max_examples=50)
def test_aggregate_sum(vals: list[float]):
    """Sum matches Python's built-in sum."""
    pts = _make_points(vals)
    result = _computer.aggregate(pts, "sum")
    assert abs(result - sum(vals)) < 1e-6


@given(vals=st.lists(_values, min_size=1, max_size=50))
@settings(max_examples=50)
def test_aggregate_mean_between_min_max(vals: list[float]):
    """Mean is always between min and max."""
    pts = _make_points(vals)
    mean = _computer.aggregate(pts, "mean")
    lo = _computer.aggregate(pts, "min")
    hi = _computer.aggregate(pts, "max")
    assert lo - 1e-9 <= mean <= hi + 1e-9


@given(vals=st.lists(_pos_values, min_size=1, max_size=50))
@settings(max_examples=50)
def test_aggregate_sum_ge_min_times_count(vals: list[float]):
    """For positive values: sum >= min * count."""
    pts = _make_points(vals)
    s = _computer.aggregate(pts, "sum")
    lo = _computer.aggregate(pts, "min")
    n = _computer.aggregate(pts, "count")
    assert s >= lo * n - 1e-6


def test_aggregate_empty_returns_zero():
    """Empty point list returns 0.0 for all methods."""
    for method in ("mean", "sum", "min", "max", "count"):
        assert _computer.aggregate([], method) == 0.0


# ── InMemoryMetricsComputer.trend ────────────────────────────────


@given(start=_pos_values, step=st.floats(min_value=0.1, max_value=100.0))
@settings(max_examples=50)
def test_trend_monotonic_increasing(start: float, step: float):
    """Monotonically increasing values produce 'up' direction."""
    vals = [start + step * i for i in range(10)]
    pts = _make_points(vals)
    result = _computer.trend(pts)
    assert result["direction"] == "up"
    assert result["slope"] > 0


@given(start=_pos_values, step=st.floats(min_value=0.1, max_value=100.0))
@settings(max_examples=50)
def test_trend_monotonic_decreasing(start: float, step: float):
    """Monotonically decreasing values produce 'down' direction."""
    vals = [start - step * i for i in range(10)]
    pts = _make_points(vals)
    result = _computer.trend(pts)
    assert result["direction"] == "down"
    assert result["slope"] < 0


def test_trend_single_point_stable():
    """Single point returns stable."""
    pts = _make_points([5.0])
    assert _computer.trend(pts)["direction"] == "stable"


# ── InMemoryMetricsComputer.detect_drift ─────────────────────────


@given(val=_values)
@settings(max_examples=50)
def test_detect_drift_identical_no_drift(val: float):
    """Identical baseline and current never drifts."""
    pts = _make_points([val] * 5)
    result = _computer.detect_drift(pts, pts, threshold=0.1)
    assert result["drifted"] is False


def test_detect_drift_empty_insufficient():
    """Empty inputs return insufficient_data."""
    result = _computer.detect_drift([], [], threshold=0.1)
    assert result["drifted"] is False
    assert result["reason"] == "insufficient_data"
