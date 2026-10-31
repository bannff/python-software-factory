"""Run-scoped typed-query delegation mixin (bd python-factory-j1lb).

Split out of ``networkx_adapter.py`` to keep that file under the 200 LOC
ceiling — thin delegating methods only; implementations stay in
``networkx_runs.py``.
"""
from __future__ import annotations

from typing import Any

from ..models import TaxonomyEdgeSpec
from ..ports import Entity, QueryResult


class NetworkXRunQueriesMixin:
    """Mixin: run-scoped queries delegating to ``networkx_runs.py``."""

    def get_findings_for_run(
        self, run_id: str, app: str = "", limit: int = 50,
        taxonomy_edges: list[TaxonomyEdgeSpec] | None = None,
    ) -> QueryResult:
        from . import networkx_runs
        return networkx_runs.get_findings_for_run(
            self, run_id, app, limit, taxonomy_edges,
        )

    def count_entities_by_run(
        self, run_id: str, labels: list[str],
    ) -> dict[str, int]:
        from . import networkx_runs
        return networkx_runs.count_entities_by_run(self, run_id, labels)

    def get_recent_findings(
        self, severity: str = "", app: str = "", run_id: str = "",
        limit: int = 50,
        taxonomy_edges: list[TaxonomyEdgeSpec] | None = None,
    ) -> QueryResult:
        from . import networkx_runs
        return networkx_runs.get_recent_findings(
            self, severity, app, run_id, limit, taxonomy_edges,
        )

    def get_target_app(
        self, target_app: str, run_id: str = "",
    ) -> Entity | None:
        from . import networkx_runs
        return networkx_runs.get_target_app(self, target_app, run_id)

    def get_tool_invocations_for_run(
        self, run_id: str, limit: int = 50,
    ) -> QueryResult:
        from . import networkx_runs
        return networkx_runs.get_tool_invocations_for_run(self, run_id, limit)

    def list_recent_tool_invocations(
        self, limit: int = 100,
    ) -> QueryResult:
        from . import networkx_runs
        return networkx_runs.list_recent_tool_invocations(self, limit)


__all__ = ["NetworkXRunQueriesMixin"]
