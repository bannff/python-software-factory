"""Ground truth entry ingestion — stores GT JSON into KB + graph.

Parses the ART GT schema and:
1. Calls kb_ingest via MCP aggregator with embedded text
2. Creates GTEntry graph node
3. Creates AppEndpoint + CodeLocation nodes linked to GTEntry
4. Creates Commit node linked to GTEntry
5. Auto-classifies GTEntry with CLASSIFIED_AS → CWECategory
"""
from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _invoke(tool_name: str, **kwargs: Any) -> Any:
    from factory.mcp_server.interface import get_server, get_aggregator
    get_server()
    agg = get_aggregator()
    if agg is None:
        raise RuntimeError("MCP aggregator not available")
    return agg.invoke_tool(tool_name, **kwargs)


def _h8(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()[:8]


def _add_node(entity_id: str, entity_type: str, props: dict) -> None:
    _invoke("graph_graph_add_entity", entity_id=entity_id,
            entity_type=entity_type, properties=props)


def _add_edge(rel_id: str, rel_type: str, src: str, tgt: str) -> None:
    _invoke("graph_graph_add_relationship", relationship_id=rel_id,
            relationship_type=rel_type, source_id=src, target_id=tgt)


def _embedded_text(gt: dict) -> str:
    parts: list[str] = []
    stmt = gt.get("ground_truth", {}).get("statement", "")
    if stmt:
        parts.append(stmt)
    for loc in gt.get("code_evidence", {}).get("locations", []):
        d = loc.get("description", "")
        if d:
            parts.append(d)
    for step in gt.get("exploit_evidence", {}).get("reproduction_steps", []):
        if isinstance(step, str) and step:
            parts.append(step)
    return "\n".join(parts)


def _ingest_kb(gt_id: str, cwe: str, service: str, text: str) -> None:
    try:
        _invoke("kb_ingest", content=text,
                metadata={"gt_id": gt_id, "cwe": cwe, "service": service},
                source=f"gt:{gt_id}")
    except Exception as e:
        logger.warning("KB ingest failed for %s: %s", gt_id, e)


def _create_gt_node(gt_id: str, gt: dict, cwe: str, service: str) -> None:
    fix = gt.get("fix_evidence", {})
    try:
        _add_node(f"gt-{gt_id}", "GTEntry", {
            "gt_id": gt_id,
            "vulnerability_class": gt.get("vulnerability_class", ""),
            "cwe": cwe,
            "confidence": gt.get("ground_truth", {}).get("confidence", ""),
            "service_name": service,
            "fix_commit": fix.get("fix_commit", ""),
            "fix_cr": fix.get("fix_cr", ""),
            "created_at": _utcnow(),
        })
    except Exception as e:
        logger.warning("GTEntry node failed for %s: %s", gt_id, e)


def _create_code_locations(gt_id: str, gt: dict) -> int:
    count = 0
    for loc in gt.get("code_evidence", {}).get("locations", []):
        fp, ls = loc.get("file", ""), loc.get("line_start", 0)
        lid = f"codeloc-{_h8(fp)}-{ls}"
        try:
            _add_node(lid, "CodeLocation", {
                "file": fp, "function": loc.get("function", ""),
                "line_start": ls, "line_end": loc.get("line_end", ls),
                "description": loc.get("description", ""),
                "created_at": _utcnow(),
            })
            _add_edge(f"has-codeloc-{gt_id}-{lid}", "HAS_CODE_LOCATION",
                      f"gt-{gt_id}", lid)
            count += 1
        except Exception as e:
            logger.warning("CodeLocation failed (%s): %s", lid, e)
    return count


def _create_endpoint(gt_id: str, gt: dict, service: str) -> bool:
    surface = gt.get("runtime_evidence", {}).get("surface", {})
    if not surface:
        return False
    ep, method = surface.get("endpoint", ""), surface.get("method", "GET")
    eid = f"endpoint-{service}-{method}-{_h8(ep)}"
    try:
        _add_node(eid, "AppEndpoint", {
            "endpoint": ep, "method": method,
            "service_name": service, "created_at": _utcnow(),
        })
        _add_edge(f"has-endpoint-{gt_id}-{eid}", "HAS_ENDPOINT",
                  f"gt-{gt_id}", eid)
        return True
    except Exception as e:
        logger.warning("AppEndpoint failed (%s): %s", eid, e)
        return False


def _create_commit(gt_id: str, gt: dict) -> bool:
    fix = gt.get("fix_evidence", {})
    h = fix.get("fix_commit", "")
    if not h:
        return False
    cid = f"commit-{h[:12]}"
    try:
        _add_node(cid, "Commit", {
            "hash": h, "cr_id": fix.get("fix_cr", ""),
            "description": fix.get("description", ""),
            "created_at": _utcnow(),
        })
        _add_edge(f"fixed-by-{gt_id}-{cid}", "FIXED_BY", f"gt-{gt_id}", cid)
        return True
    except Exception as e:
        logger.warning("Commit node failed (%s): %s", cid, e)
        return False


def ingest_gt_entry(gt_json: dict) -> dict:
    """Ingest a Ground Truth entry into KB + graph.

    Args:
        gt_json: ART GT schema dict.

    Returns:
        Summary dict with counts of nodes/edges created.
    """
    gt_id: str = gt_json.get("gt_id", gt_json.get("id", "unknown"))
    cwe: str = gt_json.get("cwe", "")
    service: str = gt_json.get("service_name", gt_json.get("service", ""))

    text = _embedded_text(gt_json)
    _ingest_kb(gt_id, cwe, service, text)
    _create_gt_node(gt_id, gt_json, cwe, service)

    code_locs = _create_code_locations(gt_id, gt_json)
    has_ep = _create_endpoint(gt_id, gt_json, service)
    has_commit = _create_commit(gt_id, gt_json)

    if cwe:
        try:
            from .cwe_taxonomy import classify_finding
            classify_finding(f"gt-{gt_id}", cwe)
        except Exception as e:
            logger.warning("CWE classification failed for %s: %s", gt_id, e)

    return {
        "success": True,
        "gt_id": gt_id,
        "kb_ingested": bool(text),
        "graph_nodes": {
            "gt_entry": 1,
            "code_locations": code_locs,
            "endpoint": int(has_ep),
            "commit": int(has_commit),
        },
        "classified_as": cwe or None,
    }
