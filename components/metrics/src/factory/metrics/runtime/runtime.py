"""MetricsRuntime — core runtime class (no FastMCP imports)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from factory.metrics.core import (
    BRICK_NAME, FEATURES, TOOL_CATEGORIES, VERSION, DataPoint, parse_duration,
)
from factory.metrics.runtime.baselines import BaselineManager
from factory.metrics.runtime.models import MetricDefinition, Snapshot
from factory.metrics.runtime.ports import MetricsComputer, MetricsStore


class MetricsRuntime:
    """Reusable metrics runtime (no FastMCP imports)."""

    def __init__(self, store: MetricsStore, computer: MetricsComputer) -> None:
        self.store = store
        self.computer = computer
        self._definitions: dict[str, MetricDefinition] = {}
        self._baseline_mgr = BaselineManager()

    # ── Registry management ────────────────────────────────────
    def register_definition(self, defn: MetricDefinition) -> None:
        self._definitions[defn.id] = defn

    def get_definition(self, metric_id: str) -> MetricDefinition | None:
        return self._definitions.get(metric_id)

    def list_definitions(self) -> list[dict[str, Any]]:
        return [d.model_dump(mode="json") for d in self._definitions.values()]

    def update_definition(self, metric_id: str, updates: dict[str, Any]) -> MetricDefinition | None:
        defn = self._definitions.get(metric_id)
        if defn is None:
            return None
        updated = defn.model_copy(update=updates)
        self._definitions[metric_id] = updated
        return updated

    def delete_definition(self, metric_id: str) -> bool:
        return self._definitions.pop(metric_id, None) is not None

    # ── Recording ──────────────────────────────────────────────
    def record(self, metric_id: str, value: float, labels: dict[str, str] | None = None) -> dict[str, Any]:
        ts = datetime.now(timezone.utc).timestamp()
        self.store.record(metric_id, value, labels, ts)
        return {"ok": True, "metric_id": metric_id, "value": value, "timestamp": ts}

    def record_batch(self, records: list[dict[str, Any]]) -> dict[str, Any]:
        recorded = 0
        for rec in records:
            self.store.record(
                rec["metric_id"], rec["value"],
                rec.get("labels"), rec.get("timestamp"),
            )
            recorded += 1
        return {"ok": True, "recorded": recorded}

    # ── Queries ────────────────────────────────────────────────
    def get_snapshot(self, metric_id: str, period: str = "24h") -> dict[str, Any]:
        now = datetime.now(timezone.utc).timestamp()
        window = parse_duration(period)
        points = self.store.query(metric_id, start=now - window, end=now)
        if not points:
            return Snapshot(metric_id=metric_id, current_value=0.0, period=period).model_dump()
        current = points[-1].value
        prev = points[0].value if len(points) > 1 else None
        trend_info = self.computer.trend(points)
        change_pct = None
        if prev is not None and prev != 0:
            change_pct = round(((current - prev) / abs(prev)) * 100, 2)
        snap = Snapshot(
            metric_id=metric_id, current_value=current,
            previous_value=prev, trend=trend_info["direction"],
            change_pct=change_pct, period=period, data_points=len(points),
        )
        return snap.model_dump()

    def get_trend(self, metric_id: str, window: str = "7d", granularity: str = "1d") -> dict[str, Any]:
        now = datetime.now(timezone.utc).timestamp()
        win_secs = parse_duration(window)
        gran_secs = parse_duration(granularity)
        points = self.store.query(metric_id, start=now - win_secs, end=now)
        buckets = self._bucketize(points, now - win_secs, now, gran_secs)
        trend_info = self.computer.trend(points)
        return {
            "metric_id": metric_id, "window": window,
            "granularity": granularity, "trend": trend_info,
            "buckets": buckets, "total_points": len(points),
        }

    def _bucketize(self, points: list[DataPoint], start: float, end: float, gran: float) -> list[dict[str, Any]]:
        buckets: list[dict[str, Any]] = []
        t = start
        while t < end:
            bucket_pts = [p for p in points if t <= p.timestamp < t + gran]
            val = self.computer.aggregate(bucket_pts, "mean") if bucket_pts else None
            buckets.append({"start": t, "end": t + gran, "value": val, "count": len(bucket_pts)})
            t += gran
        return buckets

    # ── Aggregation & drift ────────────────────────────────────
    def compute_aggregation(self, metric_id: str, method: str = "mean", period: str = "24h") -> dict[str, Any]:
        now = datetime.now(timezone.utc).timestamp()
        window = parse_duration(period)
        points = self.store.query(metric_id, start=now - window, end=now)
        value = self.computer.aggregate(points, method)
        return {"ok": True, "metric_id": metric_id, "method": method, "value": value, "points": len(points)}

    def detect_drift(
        self, metric_id: str, baseline_period: str = "7d",
        current_period: str = "24h", threshold: float = 0.1,
    ) -> dict[str, Any]:
        now = datetime.now(timezone.utc).timestamp()
        b_win = parse_duration(baseline_period)
        c_win = parse_duration(current_period)
        baseline = self.store.query(metric_id, start=now - b_win, end=now - c_win)
        current = self.store.query(metric_id, start=now - c_win, end=now)
        result = self.computer.detect_drift(baseline, current, threshold)
        result["metric_id"] = metric_id
        # Merge regression gate signal when a named baseline exists
        result.update(self._regression_signal(metric_id, current))
        return result

    def _regression_signal(
        self, metric_id: str, current_points: list[DataPoint],
    ) -> dict[str, Any]:
        """Regression gate fields from latest baseline, or None."""
        baselines = self._baseline_mgr.list_baselines(metric_id=metric_id)
        if not baselines or not current_points:
            return {"regression_signal": None}
        current_values = {metric_id: current_points[-1].value}
        cmp = self._baseline_mgr.compare_baseline(
            metric_id, current_values, baselines[-1]["tag"],
        )
        if not cmp.get("ok"):
            return {"regression_signal": None}
        return {
            "regression_signal": cmp["overall_signal"],
            "baseline_tag": cmp["baseline_tag"],
            "comparisons": cmp["comparisons"],
        }

    # ── Baselines & regression gate ───────────────────────────
    def set_baseline(self, metric_id: str, tag: str, values: dict[str, float]) -> dict[str, Any]:
        return self._baseline_mgr.set_baseline(metric_id, tag, values)

    def compare_baseline(
        self,
        metric_id: str,
        current_values: dict[str, float],
        baseline_tag: str,
        threshold_block: float = 0.05,
        threshold_warn: float = 0.02,
    ) -> dict[str, Any]:
        return self._baseline_mgr.compare_baseline(
            metric_id, current_values, baseline_tag,
            threshold_block, threshold_warn,
        )

    def list_baselines(self, metric_id: str | None = None) -> list[dict[str, Any]]:
        return self._baseline_mgr.list_baselines(metric_id)

    # ── Provenance-focused measurement ────────────────────────
    def measure_focus(self, focus: dict[str, Any]) -> Any:
        from .provenance_runtime import measure_focus
        return measure_focus(self, focus)

    # ── Contract tools ─────────────────────────────────────────
    def get_capabilities(self) -> dict[str, Any]:
        return {
            "name": BRICK_NAME, "version": VERSION,
            "features": FEATURES, "tools": TOOL_CATEGORIES,
        }

    def health_check(self) -> dict[str, Any]:
        store_health = self.store.health_check()
        return {
            "ok": store_health.get("ok", False),
            "store": store_health,
            "definitions": len(self._definitions),
        }

    def describe_config_schema(self) -> dict[str, Any]:
        return {
            "schemas": {
                "metric_definition": MetricDefinition.model_json_schema(),
                "snapshot": Snapshot.model_json_schema(),
            },
        }
