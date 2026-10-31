"""Graph-backed finding persistence via MCP aggregator.

Persists SecurityAction and Finding nodes to the graph brick.
Calls graph brick tools through the MCP aggregator — no direct
Neo4j driver usage, no cross-brick imports.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

_STRIP = frozenset({"structural_embedding", "n2v_embedding"})


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get_aggregator() -> Any:
    """Lazy-load the MCP aggregator (ensure server is initialized first)."""
    from factory.mcp_server.interface import get_server, get_aggregator
    get_server()
    return get_aggregator()


def _invoke(tool_name: str, **kwargs: Any) -> Any:
    """Invoke a graph brick tool via the MCP aggregator."""
    agg = _get_aggregator()
    if agg is None:
        raise RuntimeError("MCP aggregator not available for graph persistence")
    return agg.invoke_tool(tool_name, **kwargs)

def _rows_to_findings(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert typed finding rows into public dictionaries."""
    return [
        {key: value for key, value in row.items() if key not in _STRIP and value is not None}
        for row in rows
    ]

def _succeeded(result: Any) -> bool:
    """Return whether a canonical Graph mutation envelope succeeded."""
    return bool(result and result.ok and result.data is not None)


class GraphFindingPersistence:
    """Persist findings to Neo4j via graph brick MCP tools."""

    def persist_analysis(
        self, analysis_id: str, analysis_type: str, target: str,
        findings: list[dict[str, Any]], summary: str | None = None,
    ) -> dict[str, Any]:
        """Create SecurityAction + Finding nodes with DISCOVERED edges."""
        action_id = f"action-{analysis_id}"
        action_props: dict[str, Any] = {
            "action_type": analysis_type, "status": "completed",
            "created_at": _utcnow(), "target": target,
        }
        if summary:
            action_props["summary"] = summary
        try:
            action_result = _invoke(
                "graph_graph_add_entity", entity_id=action_id,
                entity_type="SecurityAction", properties=action_props,
            )
            if not _succeeded(action_result):
                error = getattr(action_result, "error", "missing successful graph result")
                logger.error("Failed to persist SecurityAction: %s", error)
                return {"persisted": False, "error": error}
        except Exception as e:
            logger.error("Failed to persist SecurityAction: %s", e)
            return {"persisted": False, "error": str(e)}

        from .taxonomy_enrichment import enrich_ocsf
        enrich_ocsf(action_id)

        persisted = 0
        failures: list[str] = []
        for f in findings:
            fid = f.get("id", f"finding-{analysis_id}-{persisted}")
            fprops: dict[str, Any] = {
                "severity": f.get("severity", "info"),
                "title": f.get("title", "Unknown"),
                "description": f.get("description", ""),
                "created_at": _utcnow(),
            }
            for opt in ("location", "remediation", "cwe", "evidence"):
                if f.get(opt):
                    fprops[opt] = f[opt]
            try:
                finding_result = _invoke(
                    "graph_graph_add_entity", entity_id=fid,
                    entity_type="Finding", properties=fprops,
                )
                if not _succeeded(finding_result):
                    error = getattr(finding_result, "error", "missing successful graph result")
                    logger.warning("Failed to persist finding %s: %s", fid, error)
                    failures.append(f"finding {fid}: {error}")
                    continue
                relationship_result = _invoke(
                    "graph_graph_add_relationship",
                    relationship_id=f"discovered-{action_id}-{fid}",
                    relationship_type="DISCOVERED",
                    source_id=action_id, target_id=fid,
                )
                if not _succeeded(relationship_result):
                    error = getattr(relationship_result, "error", "missing successful graph result")
                    logger.warning("Failed to persist finding relationship %s: %s", fid, error)
                    failures.append(f"relationship {fid}: {error}")
                    continue
                persisted += 1
                cwe_val = f.get("cwe")
                if cwe_val:
                    from .taxonomy_enrichment import enrich_finding_cwe
                    enrich_finding_cwe(fid, cwe_val)
                enrich_ocsf(fid)
            except Exception as e:
                logger.warning("Failed to persist finding %s: %s", fid, e)
                failures.append(f"finding {fid}: {e}")

        result = {
            "persisted": not failures, "backend": "graph",
            "analysis_id": analysis_id, "action_node": action_id,
            "findings_persisted": persisted, "findings_total": len(findings),
        }
        if failures:
            result["error"] = f"partial graph persistence: {'; '.join(failures)}"
        return result

    def get_analysis(self, analysis_id: str) -> dict[str, Any] | None:
        """Retrieve a persisted analysis from the graph."""
        action_id = f"action-{analysis_id}"
        try:
            result = _invoke("graph_graph_get_entity", entity_id=action_id)
            if not result or not result.ok or result.data is None:
                return None
            entity = result.data.entity
            if not result.data.found or entity is None:
                return None
            neighbors = _invoke(
                "graph_graph_get_neighbors", entity_id=action_id,
                relationship_type="DISCOVERED", direction="outgoing")
            neighbor_entities = (
                neighbors.data.neighbors
                if neighbors and neighbors.ok and neighbors.data is not None else []
            )
            return {
                "analysis_id": analysis_id, "action_node": action_id,
                **entity.properties,
                "findings": [neighbor.properties for neighbor in neighbor_entities],
            }
        except Exception as e:
            logger.error("Failed to get analysis %s: %s", analysis_id, e)
            return None

    def list_analyses(self, limit: int = 50) -> list[dict[str, Any]]:
        """List persisted SecurityAction nodes."""
        try:
            result = _invoke("graph_graph_find_entities",
                             entity_type="SecurityAction", limit=limit)
            if not result or not result.ok or result.data is None:
                return []
            return [
                {"analysis_id": entity.id.replace("action-", ""),
                 **{key: value for key, value in entity.properties.items()
                    if key not in _STRIP}}
                for entity in result.data.entities
            ]
        except Exception as e:
            logger.error("Failed to list analyses: %s", e)
            return []

    def get_findings(
        self, severity: str | None = None, limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Query Finding rows joined with CWE/OCSF taxonomy badges.

        Delegates to the graph brick's typed
        ``graph_graph_get_recent_findings`` tool (bd python-factory-j1lb)
        so the CWE+OCSF join executes inside the active graph adapter
        rather than via raw Cypher. Keeps the public return shape
        unchanged: ``[{id, severity, ..., cwe_id?, cwe_name?,
        ocsf_class?, ocsf_uid?}, ...]``.
        """
        try:
            result = _invoke(
                "graph_graph_get_recent_findings",
                severity=severity or "", app="", run_id="", limit=limit,
            )
            if not result or not result.ok or result.data is None:
                return []
            return _rows_to_findings(result.data.rows)
        except Exception as e:
            logger.error("Failed to get findings: %s", e)
            return []

    def health_check(self) -> dict[str, Any]:
        """Check graph brick connectivity."""
        try:
            result = _invoke("graph_graph_health_check")
            data = getattr(result, "data", None)
            return {"healthy": bool(result and result.ok and data and data.healthy),
                    "backend": "graph",
                    "graph_nodes": sum(item.nodes for item in data.graphs.values()) if data else 0}
        except Exception as e:
            return {"healthy": False, "backend": "graph", "error": str(e)}
