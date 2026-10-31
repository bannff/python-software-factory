"""Graph-backed eval persistence through the shared MCP tool invoker seam."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Callable

from ..ports import EvalMetrics, EvalRun, EvalSuite

logger = logging.getLogger(__name__)
ToolInvoker = Callable[..., Any]


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get_invoker() -> ToolInvoker | None:
    """Resolve the existing tool-invoker service without initializing a server."""
    from factory.mcp_utils.interface import get_service
    return get_service("tool_invoker")


class GraphEvalsStore:
    """Persist eval runs and suites to the graph brick through MCP tools."""

    def __init__(self, invoker: ToolInvoker | None = None) -> None:
        self._injected_invoker = invoker

    def _invoke(self, tool_name: str, **kwargs: Any) -> Any:
        invoker = (
            self._injected_invoker
            if self._injected_invoker is not None else _get_invoker()
        )
        if invoker is None:
            raise RuntimeError("tool_invoker service unavailable for graph persistence")
        return invoker(tool_name, **kwargs)

    def persist_run(self, run: EvalRun, metrics: EvalMetrics) -> None:
        """Create an EvalRun node and link it to its suite."""
        entity_id = f"eval-run-{run.id}"
        props: dict[str, Any] = {
            "suite_id": run.suite_id,
            "pass_rate": metrics.pass_rate,
            "avg_score": metrics.avg_score,
            "total_cases": metrics.total_cases,
            "failed_cases": metrics.failed,
            "run_at": (run.completed_at or run.started_at).isoformat(),
            "status": run.status,
            "created_at": _utcnow(),
        }
        if run.summary:
            props["config"] = json.dumps(run.summary)
        self._invoke(
            "graph_graph_add_entity",
            entity_id=entity_id,
            entity_type="EvalRun",
            properties=props,
        )
        self._invoke(
            "graph_graph_add_relationship",
            relationship_id=f"evaluated-by-{run.id}",
            relationship_type="EVALUATED_BY",
            source_id=f"eval-suite-{run.suite_id}",
            target_id=entity_id,
        )

    def persist_suite(self, suite: EvalSuite) -> None:
        """Create or update a lightweight suite anchor node."""
        self._invoke(
            "graph_graph_add_entity",
            entity_id=f"eval-suite-{suite.id}",
            entity_type="EvalSuite",
            properties={
                "name": suite.name,
                "description": suite.description,
                "case_count": len(suite.cases),
                "created_at": _utcnow(),
            },
        )

    def query_runs(self, suite_id: str | None = None) -> list[dict]:
        """List EvalRun entities through the portable Graph read API."""
        try:
            result = self._invoke(
                "graph_graph_find_entities", entity_type="EvalRun", limit=100,
            )
            if not result or not result.ok or result.data is None:
                return []
            rows = [dict(entity.properties) for entity in result.data.entities]
            if suite_id:
                rows = [row for row in rows if row.get("suite_id") == suite_id]
            return sorted(rows, key=lambda row: str(row.get("run_at", "")), reverse=True)
        except Exception as exc:
            logger.error("Failed to list eval runs: %s", exc)
            return []

    def health_check(self) -> dict[str, Any]:
        """Check graph backend availability."""
        try:
            result = self._invoke("graph_graph_health_check")
            data = getattr(result, "data", None)
            return {
                "ok": bool(result and result.ok and data and data.healthy),
                "backend": "graph",
                "graph_nodes": sum(item.nodes for item in data.graphs.values()) if data else 0,
            }
        except Exception as exc:
            return {"ok": False, "backend": "graph", "error": str(exc)}
