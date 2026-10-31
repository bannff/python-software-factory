"""OCSF Event Schema taxonomy seed data and graph conformance helpers.

Creates OCSFCategory + OCSFEventClass nodes and BELONGS_TO edges via the
MCP aggregator pattern — no direct Neo4j imports, no cross-brick imports.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get_invoker() -> Any:
    """Resolve the process tool invoker without importing a transport."""
    from factory.mcp_utils.registry import get_service
    return get_service("tool_invoker")


def _invoke(tool_name: str, **kwargs: Any) -> Any:
    invoker = _get_invoker()
    if invoker is None:
        raise RuntimeError("MCP tool invoker not available for OCSF taxonomy")
    return invoker(tool_name, **kwargs)


# OCSF v1.3 categories
OCSF_CATEGORIES: list[dict[str, Any]] = [
    {"category_uid": 1, "category_name": "System Activity", "description": "OS and system-level events."},
    {"category_uid": 2, "category_name": "Findings", "description": "Security findings and alerts."},
    {"category_uid": 3, "category_name": "Identity & Access Management", "description": "Authentication and authorization events."},
    {"category_uid": 4, "category_name": "Network Activity", "description": "Network communication events."},
    {"category_uid": 5, "category_name": "Discovery", "description": "Inventory and configuration discovery."},
    {"category_uid": 6, "category_name": "Application Activity", "description": "Application-level events."},
    {"category_uid": 7, "category_name": "Remediation", "description": "Remediation and response actions."},
]

# Security-relevant OCSF v1.3 event classes
OCSF_EVENT_CLASSES: list[dict[str, Any]] = [
    {"class_uid": 1001, "class_name": "File System Activity", "category_uid": 1, "description": "File creation, modification, deletion, and access events."},
    {"class_uid": 1007, "class_name": "Process Activity", "category_uid": 1, "description": "Process creation, termination, and injection events."},
    {"class_uid": 2001, "class_name": "Security Finding", "category_uid": 2, "description": "Vulnerability findings from scanners and assessments."},
    {"class_uid": 2002, "class_name": "Compliance Finding", "category_uid": 2, "description": "Compliance and policy violation findings."},
    {"class_uid": 2003, "class_name": "Detection Finding", "category_uid": 2, "description": "Threat detection and alert findings."},
    {"class_uid": 2004, "class_name": "Incident Finding", "category_uid": 2, "description": "Security incident findings."},
    {"class_uid": 3001, "class_name": "Authentication", "category_uid": 3, "description": "User and service authentication events."},
    {"class_uid": 3002, "class_name": "Authorize Session", "category_uid": 3, "description": "Session authorization and privilege events."},
    {"class_uid": 4001, "class_name": "Network Activity", "category_uid": 4, "description": "Network connection and traffic events."},
    {"class_uid": 5001, "class_name": "Device Inventory Info", "category_uid": 5, "description": "Device and asset inventory records."},
    {"class_uid": 5002, "class_name": "Device Config State", "category_uid": 5, "description": "Device configuration state snapshots."},
    {"class_uid": 6001, "class_name": "Web Resources Activity", "category_uid": 6, "description": "HTTP/web resource access events."},
    {"class_uid": 6002, "class_name": "Application Lifecycle", "category_uid": 6, "description": "Application install, update, and removal events."},
]


def _cat_entity_id(category_uid: int) -> str:
    return f"ocsf-cat-{category_uid}"


def _class_entity_id(class_uid: int) -> str:
    return f"ocsf-class-{class_uid}"


def seed_ocsf_taxonomy() -> dict[str, Any]:
    """Create OCSFCategory + OCSFEventClass nodes and BELONGS_TO edges.

    Returns counts of categories, classes, and edges created. Idempotent.
    """
    cats_created = 0
    classes_created = 0
    edges_created = 0
    now = _utcnow()

    # Pass 1: create OCSFCategory nodes
    for cat in OCSF_CATEGORIES:
        eid = _cat_entity_id(cat["category_uid"])
        props = {
            "category_uid": cat["category_uid"],
            "category_name": cat["category_name"],
            "description": cat["description"],
            "created_at": now,
        }
        try:
            _invoke("graph_graph_add_entity", entity_id=eid, entity_type="OCSFCategory", properties=props)
            cats_created += 1
        except Exception as e:
            logger.warning("Failed to create OCSFCategory %s: %s", eid, e)

    # Pass 2: create OCSFEventClass nodes
    for cls in OCSF_EVENT_CLASSES:
        eid = _class_entity_id(cls["class_uid"])
        props = {
            "class_uid": cls["class_uid"],
            "class_name": cls["class_name"],
            "category_uid": cls["category_uid"],
            "category_name": next(
                (c["category_name"] for c in OCSF_CATEGORIES if c["category_uid"] == cls["category_uid"]),
                "",
            ),
            "description": cls["description"],
            "created_at": now,
        }
        try:
            _invoke("graph_graph_add_entity", entity_id=eid, entity_type="OCSFEventClass", properties=props)
            classes_created += 1
        except Exception as e:
            logger.warning("Failed to create OCSFEventClass %s: %s", eid, e)

    # Pass 3: create BELONGS_TO edges (OCSFEventClass → OCSFCategory)
    for cls in OCSF_EVENT_CLASSES:
        class_eid = _class_entity_id(cls["class_uid"])
        cat_eid = _cat_entity_id(cls["category_uid"])
        rel_id = f"belongs-to-{class_eid}-{cat_eid}"
        try:
            _invoke(
                "graph_graph_add_relationship",
                relationship_id=rel_id,
                relationship_type="BELONGS_TO",
                source_id=class_eid,
                target_id=cat_eid,
            )
            edges_created += 1
        except Exception as e:
            logger.warning("Failed to create BELONGS_TO %s→%s: %s", class_eid, cat_eid, e)

    return {
        "categories_created": cats_created,
        "classes_created": classes_created,
        "edges_created": edges_created,
    }


def conform_finding(entity_id: str, class_uid: int) -> dict[str, Any]:
    """Create a CONFORMS_TO edge from a Finding/SecurityAction to an OCSFEventClass.

    Args:
        entity_id: Entity ID of the source node (e.g. 'finding-scan-001-0').
        class_uid: OCSF event class UID (e.g. 2001).

    Returns:
        Success/failure dict.
    """
    class_eid = _class_entity_id(class_uid)
    rel_id = f"conforms-to-{entity_id}-{class_eid}"
    try:
        _invoke(
            "graph_graph_add_relationship",
            relationship_id=rel_id,
            relationship_type="CONFORMS_TO",
            source_id=entity_id,
            target_id=class_eid,
            properties={"created_at": _utcnow()},
        )
        return {
            "success": True,
            "entity_id": entity_id,
            "class_uid": class_uid,
            "relationship_id": rel_id,
        }
    except Exception as e:
        logger.error("Failed to conform %s to class %s: %s", entity_id, class_uid, e)
        return {"success": False, "error": str(e)}
