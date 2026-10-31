"""IDOR pipeline additions to the unified graph taxonomy.

Extends GRAPH_TAXONOMY with GTEntry, AppEndpoint, CodeLocation, Commit
node types, their relationships, and entity ID conventions.
Imported and merged by docs_taxonomy.py.
"""

IDOR_NODE_TYPES: dict = {
    "GTEntry": {
        "description": (
            "Ground truth vulnerability entry. Seeded via security_ingest_gt_entry."
        ),
        "required_properties": [
            "gt_id", "vulnerability_class", "cwe", "confidence",
            "service_name", "created_at",
        ],
        "optional_properties": ["fix_commit", "fix_cr"],
        "id_convention": "gt-{gt_id}",
        "id_example": "gt-IDOR-SSAMS-001",
    },
    "AppEndpoint": {
        "description": "HTTP endpoint from GT runtime_evidence. Linked to GTEntry.",
        "required_properties": ["endpoint", "method", "service_name", "created_at"],
        "optional_properties": [],
        "id_convention": "endpoint-{service}-{method}-{path_hash[:8]}",
        "id_example": "endpoint-ssams-DELETE-a1b2c3d4",
    },
    "CodeLocation": {
        "description": "Code location from GT code_evidence. Linked to GTEntry.",
        "required_properties": [
            "file", "function", "line_start", "line_end", "description", "created_at",
        ],
        "optional_properties": [],
        "id_convention": "codeloc-{file_hash[:8]}-{line_start}",
        "id_example": "codeloc-a1b2c3d4-30",
    },
    "Commit": {
        "description": "Fix commit from GT fix_evidence. Linked to GTEntry.",
        "required_properties": ["hash", "description", "created_at"],
        "optional_properties": ["cr_id"],
        "id_convention": "commit-{hash[:12]}",
        "id_example": "commit-37c96eeae5a7",
    },
}

IDOR_RELATIONSHIP_TYPES: dict = {
    "HAS_ENDPOINT": {
        "description": "GT entry links to its vulnerable HTTP endpoint.",
        "source": "GTEntry",
        "target": "AppEndpoint",
        "properties": [],
    },
    "HAS_CODE_LOCATION": {
        "description": "GT entry links to its vulnerable code location.",
        "source": "GTEntry",
        "target": "CodeLocation",
        "properties": [],
    },
    "FIXED_BY": {
        "description": "GT entry was fixed by a commit.",
        "source": "GTEntry",
        "target": "Commit",
        "properties": [],
    },
    "EVALUATED_AGAINST": {
        "description": (
            "WorkflowRun evaluated against a GT entry. Written deterministically "
            "by the games scorer after each completed run; one edge per matched "
            "(verdict=TP) or missed (verdict=FN) GT entry. False positives have "
            "no GT to anchor against — they appear as independent Finding nodes."
        ),
        "source": "WorkflowRun",
        "target": "GTEntry",
        "properties": ["score", "verdict", "created_at"],
        "verdict_values": ["TP", "FN"],
    },
}

IDOR_ENTITY_ID_CONVENTIONS: dict = {
    "GTEntry": "gt-{gt_id}",
    "AppEndpoint": "endpoint-{service}-{method}-{path_hash[:8]}",
    "CodeLocation": "codeloc-{file_hash[:8]}-{line_start}",
    "Commit": "commit-{hash[:12]}",
}
