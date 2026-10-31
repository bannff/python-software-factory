"""Unified graph taxonomy — node types, relationships, and conventions for all graph-backed bricks."""

from .docs_taxonomy_ext import (
    EXT_ENTITY_ID_CONVENTIONS,
    EXT_NODE_TYPES,
    EXT_RELATIONSHIP_TYPES,
)
from .docs_taxonomy_idor import (
    IDOR_ENTITY_ID_CONVENTIONS,
    IDOR_NODE_TYPES,
    IDOR_RELATIONSHIP_TYPES,
)

GRAPH_TAXONOMY = {
    "version": "2.1.0",
    "description": "Unified graph taxonomy for all graph-backed bricks.",
    "node_types": {
        "SecurityAction": {
            "description": "A discrete security operation (threat model, code scan, pen-test).",
            "required_properties": ["action_type", "status", "created_at"],
            "optional_properties": ["completed_at", "config", "summary"],
            "action_types": [
                "threat_model", "code_scan", "pen_test", "recon",
                "dependency_audit", "iam_review", "network_scan",
            ],
        },
        "Agent": {
            "description": "The agent that performed work.",
            "required_properties": ["agent_name"],
            "optional_properties": ["model_id", "version", "capabilities"],
        },
        "Finding": {
            "description": "A security issue discovered during an action.",
            "required_properties": ["severity", "title", "description"],
            "optional_properties": [
                "cwe", "remediation", "affected_resource_arn",
                "evidence", "confidence", "finding_type",
            ],
            "severity_levels": ["critical", "high", "medium", "low", "info"],
            "finding_types": [
                "vulnerability", "misconfiguration", "exposure",
                "policy_violation", "weak_credential",
            ],
        },
        "EvalRun": {
            "description": "An evaluation of output quality.",
            "required_properties": ["suite_id", "pass_rate"],
            "optional_properties": [
                "avg_score", "total_cases", "failed_cases", "run_at", "config",
            ],
        },
        "Input": {
            "description": "Data fed into a security action.",
            "required_properties": ["input_type"],
            "optional_properties": [
                "blob_ref", "content_hash", "source", "format", "size_bytes",
            ],
            "input_types": [
                "source_code", "config_file", "iam_policy",
                "network_topology", "dependency_manifest", "api_spec",
            ],
        },
        "Output": {
            "description": "An artifact produced by a security action.",
            "required_properties": ["output_type"],
            "optional_properties": [
                "blob_ref", "content_hash", "format", "size_bytes", "summary",
            ],
            "output_types": [
                "threat_model_report", "scan_report", "pen_test_report",
                "remediation_plan", "risk_assessment",
            ],
        },
        "AppReference": {
            "description": "Lightweight pointer to an application in an external topology graph.",
            "required_properties": ["app_name"],
            "optional_properties": [
                "topology_query", "account_id", "region", "environment", "owner",
            ],
        },
        # --- Memory domain ---
        "Memory": {
            "description": "An agent memory stored with A-MEM evolution.",
            "required_properties": ["memory_id", "content", "category", "user_id", "created_at"],
            "optional_properties": ["keywords", "context", "tags", "embedding", "evolved"],
            "categories": ["preference", "fact", "summary", "context", "custom"],
        },
        # --- Knowledge base domain ---
        "KBDocument": {
            "description": "A knowledge base document with semantic embeddings.",
            "required_properties": ["doc_id", "content"],
            "optional_properties": ["metadata", "embedding", "node_label", "collection"],
        },
        # --- Events domain ---
        "Event": {
            "description": "A system or agent event.",
            "required_properties": ["event_type", "timestamp"],
            "optional_properties": ["source", "payload", "severity"],
        },
        # --- Storage domain ---
        "Document": {
            "description": "A stored document or artifact.",
            "required_properties": ["doc_id"],
            "optional_properties": ["collection", "content_type", "size_bytes", "blob_ref"],
        },
    },
    "relationship_types": {
        "PERFORMED": {
            "description": "Agent performed a security action.",
            "source": "Agent", "target": "SecurityAction",
        },
        "TARGETED": {
            "description": "Security action targeted an application.",
            "source": "SecurityAction", "target": "AppReference",
        },
        "USED_INPUT": {
            "description": "Security action consumed an input.",
            "source": "SecurityAction", "target": "Input",
        },
        "PRODUCED": {
            "description": "Security action produced an output.",
            "source": "SecurityAction", "target": "Output",
        },
        "DISCOVERED": {
            "description": "Security action discovered a finding.",
            "source": "SecurityAction", "target": "Finding",
        },
        "AFFECTS": {
            "description": "Finding affects an application.",
            "source": "Finding", "target": "AppReference",
        },
        "EVALUATED_BY": {
            "description": "Output was evaluated by an eval run.",
            "source": "Output", "target": "EvalRun",
        },
        "DERIVED_FROM": {
            "description": "Input derived from a previous output (chains actions).",
            "source": "Input", "target": "Output",
        },
        "HAS_MEMORY": {
            "description": "Agent has a stored memory.",
            "source": "Agent", "target": "Memory",
        },
        "RELATED_TO": {
            "description": "Semantically related memories or cross-domain links.",
            "source": "Memory", "target": "Memory",
        },
        "EVOLVED_FROM": {
            "description": "Memory evolved from a previous version.",
            "source": "Memory", "target": "Memory",
        },
        "FOLLOWED_BY": {
            "description": "Temporal sequence of memories.",
            "source": "Memory", "target": "Memory",
        },
        "CAUSED_BY": {
            "description": "Event caused by another event.",
            "source": "Event", "target": "Event",
        },
        "FROM_SOURCE": {
            "description": "Event originated from an agent.",
            "source": "Event", "target": "Agent",
        },
        "REFERENCES": {
            "description": "Memory references a KB document.",
            "source": "Memory", "target": "KBDocument",
        },
        "MENTIONS": {
            "description": "Memory mentions a security finding.",
            "source": "Memory", "target": "Finding",
        },
    },
    "conventions": {
        "id_format": "Type-prefixed kebab-case (e.g. agent-001, finding-042, mem-abc).",
        "external_refs": (
            "S3 blobs via 'blob_ref', external applications via "
            "'app_name'/'topology_query', AWS resources via "
            "'affected_resource_arn'."
        ),
        "timestamps": "ISO-8601 strings in 'created_at'/'completed_at'/'timestamp'.",
        "embeddings": (
            "Semantic: 'embedding' (1024-dim Bedrock Titan v2). "
            "Structural: 'structural_embedding' (GDS FastRP/node2Vec)."
        ),
        "cross_domain": (
            "Cross-domain edges (REFERENCES, MENTIONS, HAS_MEMORY, FROM_SOURCE) "
            "link nodes across security, memory, KB, and events domains."
        ),
        "entity_id_conventions": {
            **IDOR_ENTITY_ID_CONVENTIONS,
            **EXT_ENTITY_ID_CONVENTIONS,
        },
    },
}

# Merge IDOR pipeline, CWE, OCSF, Games, and Metrics additions
GRAPH_TAXONOMY["node_types"].update({**IDOR_NODE_TYPES, **EXT_NODE_TYPES})
GRAPH_TAXONOMY["relationship_types"].update({**IDOR_RELATIONSHIP_TYPES, **EXT_RELATIONSHIP_TYPES})
