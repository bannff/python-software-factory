"""CWE taxonomy seed data and graph classification helpers.

Creates CWECategory nodes and CHILD_OF / CLASSIFIED_AS edges via the
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
        raise RuntimeError("MCP tool invoker not available for CWE taxonomy")
    return invoker(tool_name, **kwargs)


# ~30 top CWE entries covering OWASP Top 10 + CWE Top 25 overlap.
# parent_cwe references form the CHILD_OF hierarchy.
CWE_SEED_DATA: list[dict[str, Any]] = [
    # --- Pillar / class categories ---
    {"cwe_id": "CWE-707", "name": "Improper Neutralization", "description": "Failure to ensure input is safe before use.", "parent_cwe": None},
    {"cwe_id": "CWE-664", "name": "Improper Control of a Resource Through its Lifetime", "description": "Resource lifecycle mismanagement.", "parent_cwe": None},
    {"cwe_id": "CWE-693", "name": "Protection Mechanism Failure", "description": "Security mechanism is missing or incorrectly applied.", "parent_cwe": None},
    {"cwe_id": "CWE-682", "name": "Incorrect Calculation", "description": "Computation produces incorrect results.", "parent_cwe": None},
    {"cwe_id": "CWE-710", "name": "Improper Adherence to Coding Standards", "description": "Code does not follow required conventions.", "parent_cwe": None},
    # --- Injection family (children of CWE-707) ---
    {"cwe_id": "CWE-74", "name": "Injection", "description": "Untrusted data sent to an interpreter as part of a command or query.", "parent_cwe": "CWE-707"},
    {"cwe_id": "CWE-79", "name": "Cross-site Scripting (XSS)", "description": "Improper neutralization of input during web page generation.", "parent_cwe": "CWE-74"},
    {"cwe_id": "CWE-89", "name": "SQL Injection", "description": "Improper neutralization of special elements in SQL commands.", "parent_cwe": "CWE-74"},
    {"cwe_id": "CWE-78", "name": "OS Command Injection", "description": "Improper neutralization of special elements in OS commands.", "parent_cwe": "CWE-74"},
    {"cwe_id": "CWE-77", "name": "Command Injection", "description": "Improper neutralization of special elements in a command.", "parent_cwe": "CWE-74"},
    {"cwe_id": "CWE-94", "name": "Code Injection", "description": "Improper control of code generation.", "parent_cwe": "CWE-74"},
    {"cwe_id": "CWE-917", "name": "Expression Language Injection", "description": "Improper neutralization in expression language statements.", "parent_cwe": "CWE-94"},
    # --- Auth / access control ---
    {"cwe_id": "CWE-287", "name": "Improper Authentication", "description": "Failure to prove identity claim.", "parent_cwe": "CWE-693"},
    {"cwe_id": "CWE-306", "name": "Missing Authentication for Critical Function", "description": "No authentication on a sensitive operation.", "parent_cwe": "CWE-287"},
    {"cwe_id": "CWE-862", "name": "Missing Authorization", "description": "No authorization check performed.", "parent_cwe": "CWE-693"},
    {"cwe_id": "CWE-863", "name": "Incorrect Authorization", "description": "Authorization check is present but flawed.", "parent_cwe": "CWE-693"},
    {"cwe_id": "CWE-269", "name": "Improper Privilege Management", "description": "Privileges are not correctly assigned or managed.", "parent_cwe": "CWE-693"},
    # --- Memory / resource ---
    {"cwe_id": "CWE-119", "name": "Buffer Overflow", "description": "Operations on a buffer without proper bounds checking.", "parent_cwe": "CWE-664"},
    {"cwe_id": "CWE-125", "name": "Out-of-bounds Read", "description": "Reading data past the end of a buffer.", "parent_cwe": "CWE-119"},
    {"cwe_id": "CWE-787", "name": "Out-of-bounds Write", "description": "Writing data past the end of a buffer.", "parent_cwe": "CWE-119"},
    {"cwe_id": "CWE-416", "name": "Use After Free", "description": "Referencing memory after it has been freed.", "parent_cwe": "CWE-664"},
    {"cwe_id": "CWE-476", "name": "NULL Pointer Dereference", "description": "Dereferencing a pointer that is NULL.", "parent_cwe": "CWE-664"},
    {"cwe_id": "CWE-190", "name": "Integer Overflow", "description": "Integer value wraps or overflows.", "parent_cwe": "CWE-682"},
    # --- Crypto / data exposure ---
    {"cwe_id": "CWE-200", "name": "Exposure of Sensitive Information", "description": "Sensitive data disclosed to unauthorized actors.", "parent_cwe": "CWE-664"},
    {"cwe_id": "CWE-327", "name": "Use of Broken Crypto Algorithm", "description": "Use of a cryptographic algorithm that is insufficient.", "parent_cwe": "CWE-693"},
    {"cwe_id": "CWE-798", "name": "Use of Hard-coded Credentials", "description": "Credentials embedded in source code.", "parent_cwe": "CWE-287"},
    # --- Deserialization / SSRF / path traversal ---
    {"cwe_id": "CWE-502", "name": "Deserialization of Untrusted Data", "description": "Deserializing data from untrusted sources.", "parent_cwe": "CWE-664"},
    {"cwe_id": "CWE-918", "name": "Server-Side Request Forgery (SSRF)", "description": "Server fetches a URL controlled by an attacker.", "parent_cwe": "CWE-74"},
    {"cwe_id": "CWE-22", "name": "Path Traversal", "description": "Improper limitation of a pathname to a restricted directory.", "parent_cwe": "CWE-707"},
    # --- Misconfiguration / logging ---
    {"cwe_id": "CWE-732", "name": "Incorrect Permission Assignment", "description": "Resource permissions are too permissive.", "parent_cwe": "CWE-693"},
    {"cwe_id": "CWE-352", "name": "Cross-Site Request Forgery (CSRF)", "description": "Web app does not verify request origin.", "parent_cwe": "CWE-693"},
]


def _cwe_entity_id(cwe_id: str) -> str:
    """Convert 'CWE-79' → 'cwe-79'."""
    numeric = cwe_id.split("-", 1)[1] if "-" in cwe_id else cwe_id
    return f"cwe-{numeric}"


def seed_cwe_taxonomy() -> dict[str, Any]:
    """Create CWECategory nodes and CHILD_OF edges from seed data.

    Returns counts of nodes and edges created.
    """
    nodes_created = 0
    edges_created = 0
    now = _utcnow()

    for entry in CWE_SEED_DATA:
        eid = _cwe_entity_id(entry["cwe_id"])
        props: dict[str, Any] = {
            "cwe_id": entry["cwe_id"],
            "name": entry["name"],
            "description": entry["description"],
            "created_at": now,
        }
        if entry.get("parent_cwe"):
            props["parent_cwe"] = entry["parent_cwe"]

        try:
            _invoke(
                "graph_graph_add_entity",
                entity_id=eid,
                entity_type="CWECategory",
                properties=props,
            )
            nodes_created += 1
        except Exception as e:
            logger.warning("Failed to create CWECategory %s: %s", eid, e)

    # Second pass: create CHILD_OF edges
    for entry in CWE_SEED_DATA:
        if not entry.get("parent_cwe"):
            continue
        child_id = _cwe_entity_id(entry["cwe_id"])
        parent_id = _cwe_entity_id(entry["parent_cwe"])
        rel_id = f"child-of-{child_id}-{parent_id}"
        try:
            _invoke(
                "graph_graph_add_relationship",
                relationship_id=rel_id,
                relationship_type="CHILD_OF",
                source_id=child_id,
                target_id=parent_id,
            )
            edges_created += 1
        except Exception as e:
            logger.warning("Failed to create CHILD_OF %s→%s: %s", child_id, parent_id, e)

    return {"nodes_created": nodes_created, "edges_created": edges_created}


def classify_finding(finding_id: str, cwe_id: str) -> dict[str, Any]:
    """Create a CLASSIFIED_AS edge from a Finding to a CWECategory.

    Args:
        finding_id: Entity ID of the Finding node (e.g. 'finding-scan-001-0').
        cwe_id: CWE identifier (e.g. 'CWE-79').

    Returns:
        Success/failure dict.
    """
    cwe_entity_id = _cwe_entity_id(cwe_id)
    rel_id = f"classified-{finding_id}-{cwe_entity_id}"
    try:
        _invoke(
            "graph_graph_add_relationship",
            relationship_id=rel_id,
            relationship_type="CLASSIFIED_AS",
            source_id=finding_id,
            target_id=cwe_entity_id,
            properties={"created_at": _utcnow()},
        )
        return {
            "success": True,
            "finding_id": finding_id,
            "cwe_id": cwe_id,
            "relationship_id": rel_id,
        }
    except Exception as e:
        logger.error("Failed to classify %s as %s: %s", finding_id, cwe_id, e)
        return {"success": False, "error": str(e)}
