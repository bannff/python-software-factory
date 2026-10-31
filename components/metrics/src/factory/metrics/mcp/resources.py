"""MCP resources for metrics module."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from typing import Any

from .docs import get_doc, list_docs
from ..runtime.models import DataPointModel, MetricDefinition, Snapshot

if TYPE_CHECKING:
    from ..runtime.runtime import MetricsRuntime


def register(mcp: Any, runtime: "MetricsRuntime") -> None:
    """Register MCP resources for metrics."""

    # ── Schema resources ─────────────────────────────────────────

    @mcp.resource("metrics://schemas/metric-definition")
    def get_metric_definition_schema() -> str:
        """JSON schema for MetricDefinition."""
        return json.dumps(MetricDefinition.model_json_schema(), indent=2)

    @mcp.resource("metrics://schemas/data-point")
    def get_data_point_schema() -> str:
        """JSON schema for DataPoint."""
        return json.dumps(DataPointModel.model_json_schema(), indent=2)

    @mcp.resource("metrics://schemas/snapshot")
    def get_snapshot_schema() -> str:
        """JSON schema for Snapshot."""
        return json.dumps(Snapshot.model_json_schema(), indent=2)

    # ── Documentation resources ──────────────────────────────────

    @mcp.resource("metrics://docs/overview")
    def get_overview_doc() -> str:
        """Overview documentation."""
        return get_doc("overview") or "Documentation not found"

    @mcp.resource("metrics://docs/metric-types")
    def get_metric_types_doc() -> str:
        """Metric types documentation."""
        return get_doc("metric-types") or "Documentation not found"

    # ── Live data resources ──────────────────────────────────────

    @mcp.resource("metrics://registry")
    def get_registry_resource() -> str:
        """Live list of all registered metric definitions."""
        defs = runtime.list_definitions()
        return json.dumps({"definitions": defs, "count": len(defs)}, indent=2)

    @mcp.resource("metrics://snapshots")
    def get_snapshots_resource() -> str:
        """Live snapshots of all tracked metrics."""
        snapshots = []
        for defn in runtime.list_definitions():
            snap = runtime.get_snapshot(defn["id"])
            snapshots.append(snap)
        return json.dumps({"snapshots": snapshots, "count": len(snapshots)}, indent=2)

    # ── Factory cross-reference ──────────────────────────────────

    @mcp.resource("metrics://factory")
    def get_factory_reference() -> str:
        """Cross-reference to related bricks."""
        return json.dumps({
            "brick": "metrics",
            "namespace": "factory.metrics",
            "related_bricks": [
                {"name": "telemetry", "purpose": "OTLP observability and tracing"},
                {"name": "evals", "purpose": "Agent evaluation scoring"},
                {"name": "security", "purpose": "Security finding metrics"},
                {"name": "workflow", "purpose": "Workflow execution metrics"},
            ],
        }, indent=2)
