"""In-memory adapter for metrics store and computer.

Suitable for development and testing. Not for production use.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from factory.metrics.core import DataPoint
from factory.metrics.runtime.ports import SourceObservation


class InMemoryMetricsStore:
    """In-memory implementation of MetricsStore protocol."""

    def __init__(self, source_observation: SourceObservation | None = None) -> None:
        self._data: dict[str, list[DataPoint]] = {}
        self._source_observation = source_observation or SourceObservation(
            disposition="available",
        )

    def record(
        self,
        metric_id: str,
        value: float,
        labels: dict[str, str] | None = None,
        timestamp: float | None = None,
    ) -> None:
        ts = timestamp or datetime.now(timezone.utc).timestamp()
        point = DataPoint(
            metric_id=metric_id,
            value=value,
            labels=labels or {},
            timestamp=ts,
        )
        self._data.setdefault(metric_id, []).append(point)

    def query(
        self,
        metric_id: str,
        start: float | None = None,
        end: float | None = None,
        labels: dict[str, str] | None = None,
    ) -> list[DataPoint]:
        points = self._data.get(metric_id, [])
        if start is not None:
            points = [p for p in points if p.timestamp >= start]
        if end is not None:
            points = [p for p in points if p.timestamp <= end]
        if labels:
            points = [
                p for p in points
                if all(p.labels.get(k) == v for k, v in labels.items())
            ]
        return sorted(points, key=lambda p: p.timestamp)

    def observe_source(
        self,
        labels: dict[str, str] | None = None,
        start: float | None = None,
        end: float | None = None,
    ) -> SourceObservation:
        """Return the explicit lifecycle observation configured for this store."""
        return self._source_observation

    def set_source_observation(self, observation: SourceObservation) -> None:
        """Set the explicit lifecycle observation used by subsequent queries."""
        self._source_observation = observation

    def latest(
        self,
        metric_id: str,
        labels: dict[str, str] | None = None,
    ) -> DataPoint | None:
        points = self.query(metric_id, labels=labels)
        return points[-1] if points else None

    def count(self, metric_id: str | None = None) -> int:
        if metric_id:
            return len(self._data.get(metric_id, []))
        return sum(len(pts) for pts in self._data.values())

    def list_metric_ids(self) -> list[str]:
        """Return metric identifiers available for subject-scoped queries."""
        return sorted(self._data)

    def health_check(self) -> dict[str, Any]:
        return {
            "ok": True,
            "backend": "memory",
            "metric_ids": len(self._data),
            "total_points": self.count(),
        }


class InMemoryMetricsComputer:
    """In-memory implementation of MetricsComputer protocol."""

    def aggregate(
        self, points: list[DataPoint], method: str = "mean",
    ) -> float:
        if not points:
            return 0.0
        values = [p.value for p in points]
        methods = {
            "mean": lambda v: sum(v) / len(v),
            "sum": sum,
            "min": min,
            "max": max,
            "count": lambda v: float(len(v)),
        }
        fn = methods.get(method)
        if fn is None:
            raise ValueError(f"Unknown aggregation method: {method}")
        return fn(values)

    def trend(self, points: list[DataPoint]) -> dict[str, Any]:
        if len(points) < 2:
            return {"direction": "stable", "slope": 0.0, "points": len(points)}
        values = [p.value for p in sorted(points, key=lambda p: p.timestamp)]
        n = len(values)
        x_mean = (n - 1) / 2.0
        y_mean = sum(values) / n
        num = sum((i - x_mean) * (v - y_mean) for i, v in enumerate(values))
        den = sum((i - x_mean) ** 2 for i in range(n))
        slope = num / den if den != 0 else 0.0
        direction = "up" if slope > 0.01 else ("down" if slope < -0.01 else "stable")
        return {"direction": direction, "slope": round(slope, 6), "points": n}

    def detect_drift(
        self,
        baseline: list[DataPoint],
        current: list[DataPoint],
        threshold: float = 0.1,
    ) -> dict[str, Any]:
        if not baseline or not current:
            return {"drifted": False, "reason": "insufficient_data"}
        b_mean = sum(p.value for p in baseline) / len(baseline)
        c_mean = sum(p.value for p in current) / len(current)
        if b_mean == 0:
            delta = abs(c_mean)
        else:
            delta = abs(c_mean - b_mean) / abs(b_mean)
        return {
            "drifted": delta > threshold,
            "baseline_mean": round(b_mean, 6),
            "current_mean": round(c_mean, 6),
            "delta_pct": round(delta * 100, 2),
            "threshold_pct": round(threshold * 100, 2),
        }
