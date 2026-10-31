"""End-to-end round-trip tests for GraphFindingPersistence on the typed read path.

Tracked under bd python-factory-o9l2 / epic python-factory-kzd8.

Uses an in-process fake aggregator that dispatches to a real
``GraphRuntime`` networkx adapter (no MCP server boot, no HTTP) for the
four tool names ``graph_persistence`` actually calls. This is the
spine canary for the L2 migration: persist via ``persist_analysis``,
read back via ``get_findings`` (which now goes through
``graph_graph_get_recent_findings``), and assert the public contract
holds — including the CWE/OCSF taxonomy join surfacing badges.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest

from factory.graph.mcp.core_models import EntityData, RelationshipData
from factory.graph.mcp.evidence_models import RowsData
from factory.graph.runtime.ports import Entity, Relationship
from factory.graph.runtime.runtime import GraphRuntime
from factory.mcp_utils.runtime.tool_result import ok
from factory.security.runtime.adapters.graph_persistence import (
    GraphFindingPersistence,
)

_GET_AGG = "factory.security.runtime.adapters.graph_persistence._get_aggregator"


class _NetworkXFakeAggregator:
    """Minimal aggregator dispatching to a real networkx graph adapter."""

    def __init__(self) -> None:
        self.runtime = GraphRuntime(config={"default_backend": "networkx"})
        self.graph = self.runtime.get_graph("networkx")

    def invoke_tool(self, tool_name: str, **kwargs: Any) -> Any:
        if tool_name == "graph_graph_add_entity":
            entity = self.graph.add_entity(Entity(
                id=kwargs["entity_id"],
                type=kwargs["entity_type"],
                properties=kwargs.get("properties") or {},
                labels=kwargs.get("labels") or [],
            ))
            return ok(EntityData(id=entity.id, type=entity.type,
                                 properties=entity.properties, labels=entity.labels))
        if tool_name == "graph_graph_add_relationship":
            rel = self.graph.add_relationship(Relationship(
                id=kwargs["relationship_id"],
                type=kwargs["relationship_type"],
                source_id=kwargs["source_id"],
                target_id=kwargs["target_id"],
                properties=kwargs.get("properties") or {},
            ))
            return ok(RelationshipData(id=rel.id, type=rel.type, source_id=rel.source_id,
                                       target_id=rel.target_id, properties=rel.properties))
        if tool_name == "graph_graph_get_recent_findings":
            result = self.graph.get_recent_findings(
                kwargs.get("severity", ""),
                kwargs.get("app", ""),
                kwargs.get("run_id", ""),
                int(kwargs.get("limit", 50)),
            )
            rows = list(result.raw or [])
            return ok(RowsData(rows=rows, count=len(rows)))
        if tool_name == "graph_graph_health_check":
            return {"healthy": True, "node_count": self.graph.health_check().get("node_count", 0)}
        raise AssertionError(f"unexpected tool: {tool_name}")


@pytest.fixture()
def real_agg() -> _NetworkXFakeAggregator:
    return _NetworkXFakeAggregator()


@pytest.fixture()
def persistence(real_agg: _NetworkXFakeAggregator) -> GraphFindingPersistence:
    with patch(_GET_AGG, return_value=real_agg):
        yield GraphFindingPersistence()


class TestRoundTripPersistThenRead:

    def test_persist_then_get_findings_returns_persisted(
        self, persistence: GraphFindingPersistence,
    ) -> None:
        persistence.persist_analysis(
            "scan-001", "code_analysis", "/src",
            [
                {"id": "f1", "severity": "high", "title": "SQLi",
                 "description": "Unsanitized input"},
                {"id": "f2", "severity": "low", "title": "Debug flag",
                 "description": "DEBUG=True"},
            ],
            "ok",
        )
        rows = persistence.get_findings(limit=50)
        ids = {r["id"] for r in rows}
        assert ids == {"f1", "f2"}
        by_id = {r["id"]: r for r in rows}
        assert by_id["f1"]["severity"] == "high"
        assert by_id["f1"]["title"] == "SQLi"
        assert by_id["f2"]["severity"] == "low"

    def test_severity_filter_returns_only_matching(
        self, persistence: GraphFindingPersistence,
    ) -> None:
        persistence.persist_analysis(
            "scan-002", "scan", "/src",
            [
                {"id": "fa", "severity": "critical", "title": "RCE"},
                {"id": "fb", "severity": "low", "title": "minor"},
                {"id": "fc", "severity": "critical", "title": "SSRF"},
            ],
        )
        criticals = persistence.get_findings(severity="critical")
        assert {r["id"] for r in criticals} == {"fa", "fc"}
        for r in criticals:
            assert r["severity"] == "critical"

    @pytest.mark.parametrize("limit", [0, 1, 3, 5, 50])
    def test_limit_invariant_holds(
        self, persistence: GraphFindingPersistence, limit: int,
    ) -> None:
        persistence.persist_analysis(
            "scan-003", "scan", "/src",
            [{"id": f"f{i}", "severity": "low", "title": f"t{i}"} for i in range(10)],
        )
        rows = persistence.get_findings(limit=limit)
        assert len(rows) <= limit

    def test_empty_when_nothing_persisted(
        self, persistence: GraphFindingPersistence,
    ) -> None:
        assert persistence.get_findings() == []


class TestTaxonomyJoinSurfacesBadges:

    def test_cwe_classified_as_edge_surfaces_badge(
        self,
        real_agg: _NetworkXFakeAggregator,
        persistence: GraphFindingPersistence,
    ) -> None:
        persistence.persist_analysis(
            "scan-cwe", "scan", "/src",
            [{"id": "f-xss", "severity": "high", "title": "Reflected XSS",
              "description": "alert(1)", "cwe": "CWE-79"}],
        )
        # Ensure the CWE category target node exists for the join.
        # (taxonomy_enrichment swallows missing-node failures.)
        real_agg.graph.add_entity(Entity(
            id="cwe-79", type="CWECategory",
            properties={"cwe_id": "CWE-79", "name": "Cross-site Scripting (XSS)"},
        ))
        real_agg.graph.add_relationship(Relationship(
            id="classified-f-xss-cwe-79",
            type="CLASSIFIED_AS",
            source_id="f-xss", target_id="cwe-79",
        ))
        rows = persistence.get_findings(severity="high")
        assert len(rows) == 1
        assert rows[0]["cwe_id"] == "CWE-79"
        assert rows[0]["cwe_name"] == "Cross-site Scripting (XSS)"

    def test_ocsf_conforms_to_edge_surfaces_class(
        self,
        real_agg: _NetworkXFakeAggregator,
        persistence: GraphFindingPersistence,
    ) -> None:
        persistence.persist_analysis(
            "scan-ocsf", "scan", "/src",
            [{"id": "f-ocsf", "severity": "medium", "title": "Generic finding"}],
        )
        real_agg.graph.add_entity(Entity(
            id="ocsf-class-2001", type="OCSFEventClass",
            properties={"class_uid": 2001, "class_name": "Security Finding"},
        ))
        real_agg.graph.add_relationship(Relationship(
            id="conforms-f-ocsf-2001",
            type="CONFORMS_TO",
            source_id="f-ocsf", target_id="ocsf-class-2001",
        ))
        rows = persistence.get_findings()
        row = next(r for r in rows if r["id"] == "f-ocsf")
        assert row["ocsf_class"] == "Security Finding"
        assert row["ocsf_uid"] == 2001
