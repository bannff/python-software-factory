"""Baseline management — storage, comparison, and graph persistence.

Extracted from MetricsRuntime to respect the <200 LOC constraint.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from factory.metrics.runtime.models import Baseline
from factory.metrics.runtime.regression import compare_to_baseline

logger = logging.getLogger(__name__)


class BaselineManager:
    """In-memory baseline store with best-effort graph persistence."""

    def __init__(self) -> None:
        self._baselines: dict[str, Baseline] = {}  # key: "{metric_id}:{tag}"

    def set_baseline(
        self, metric_id: str, tag: str, values: dict[str, float],
    ) -> dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        bl = Baseline(metric_id=metric_id, tag=tag, values=values, created_at=now)
        self._baselines[f"{metric_id}:{tag}"] = bl
        _persist_baseline(bl)
        return {"ok": True, "metric_id": metric_id, "tag": tag, "created_at": now}

    def compare_baseline(
        self,
        metric_id: str,
        current_values: dict[str, float],
        baseline_tag: str,
        threshold_block: float = 0.05,
        threshold_warn: float = 0.02,
    ) -> dict[str, Any]:
        key = f"{metric_id}:{baseline_tag}"
        bl = self._baselines.get(key)
        if bl is None:
            return {"ok": False, "error": f"Baseline not found: {key}"}
        result = compare_to_baseline(
            current_values, bl.values, baseline_tag,
            threshold_block, threshold_warn,
        )
        return {
            "ok": True,
            "overall_signal": result.overall_signal,
            "baseline_tag": result.baseline_tag,
            "compared_at": result.compared_at,
            "comparisons": [
                {
                    "metric_id": c.metric_id,
                    "current_value": c.current_value,
                    "baseline_value": c.baseline_value,
                    "delta": c.delta,
                    "delta_pct": c.delta_pct,
                    "signal": c.signal,
                }
                for c in result.comparisons
            ],
        }

    def list_baselines(
        self, metric_id: str | None = None,
    ) -> list[dict[str, Any]]:
        results = []
        for bl in self._baselines.values():
            if metric_id and bl.metric_id != metric_id:
                continue
            results.append(bl.model_dump(mode="json"))
        return results


def _persist_baseline(bl: Baseline) -> None:
    """Best-effort projection through portable Graph MCP mutations."""
    try:
        from factory.mcp_server.interface import get_aggregator, get_server

        get_server()
        aggregator = get_aggregator()
        if aggregator is None:
            raise RuntimeError("MCP aggregator unavailable")
        entity_id = f"baseline-{bl.metric_id}-{bl.tag}"
        aggregator.invoke_tool(
            "graph_graph_add_entity",
            entity_id=entity_id,
            entity_type="Baseline",
            properties={
                "metric_id": bl.metric_id,
                "tag": bl.tag,
                "values": json.dumps(bl.values),
                "created_at": bl.created_at,
            },
        )
        aggregator.invoke_tool(
            "graph_graph_add_relationship",
            relationship_id=f"baseline-of-{entity_id}",
            relationship_type="BASELINE_OF",
            source_id=entity_id,
            target_id=f"metric-def-{bl.metric_id}",
        )
    except Exception:
        logger.debug("Graph persistence skipped for baseline %s:%s", bl.metric_id, bl.tag)
