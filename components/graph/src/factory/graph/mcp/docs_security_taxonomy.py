"""Security-focused taxonomy view — served at graph://schemas/security-taxonomy.

Assembles a focused schema from GRAPH_TAXONOMY covering the full security
pipeline: IDOR nodes, CWE taxonomy, OCSF event schema, Games, and Metrics.
Imported by resources.py; built after GRAPH_TAXONOMY merges are complete.
"""

from .docs_taxonomy import GRAPH_TAXONOMY
from .docs_taxonomy_ext import EXT_NODE_TYPES, EXT_RELATIONSHIP_TYPES
from .docs_taxonomy_idor import IDOR_NODE_TYPES, IDOR_RELATIONSHIP_TYPES

SECURITY_TAXONOMY: dict = {
    "version": GRAPH_TAXONOMY["version"],
    "description": (
        "Full security graph taxonomy: IDOR pipeline, CWE, OCSF, Games, "
        "and Metrics nodes with all relationship types."
    ),
    "node_labels": {
        "SecurityAction": GRAPH_TAXONOMY["node_types"]["SecurityAction"],
        "Finding": GRAPH_TAXONOMY["node_types"]["Finding"],
        # IDOR Pipeline
        **{k: IDOR_NODE_TYPES[k] for k in ("GTEntry", "AppEndpoint", "CodeLocation", "Commit")},
        # CWE Taxonomy
        "CWECategory": EXT_NODE_TYPES["CWECategory"],
        # OCSF Event Schema
        "OCSFEventClass": EXT_NODE_TYPES["OCSFEventClass"],
        "OCSFCategory": EXT_NODE_TYPES["OCSFCategory"],
        # Games brick
        "GameSession": EXT_NODE_TYPES["GameSession"],
        "GameMove": EXT_NODE_TYPES["GameMove"],
        # Metrics brick
        "Baseline": EXT_NODE_TYPES["Baseline"],
    },
    "relationship_types": {
        "DISCOVERED": GRAPH_TAXONOMY["relationship_types"]["DISCOVERED"],
        # IDOR Pipeline
        **{k: IDOR_RELATIONSHIP_TYPES[k]
           for k in ("HAS_ENDPOINT", "HAS_CODE_LOCATION", "FIXED_BY", "EVALUATED_AGAINST")},
        # CWE
        "CLASSIFIED_AS": EXT_RELATIONSHIP_TYPES["CLASSIFIED_AS"],
        "CHILD_OF": EXT_RELATIONSHIP_TYPES["CHILD_OF"],
        # OCSF
        "CONFORMS_TO": EXT_RELATIONSHIP_TYPES["CONFORMS_TO"],
        "BELONGS_TO": EXT_RELATIONSHIP_TYPES["BELONGS_TO"],
        # Games
        "HAS_MOVE": EXT_RELATIONSHIP_TYPES["HAS_MOVE"],
        # Metrics
        "BASELINE_OF": EXT_RELATIONSHIP_TYPES["BASELINE_OF"],
        "COMPARED_TO": EXT_RELATIONSHIP_TYPES["COMPARED_TO"],
    },
    "entity_id_conventions": GRAPH_TAXONOMY["conventions"]["entity_id_conventions"],
    "conventions": {
        "timestamps": GRAPH_TAXONOMY["conventions"]["timestamps"],
        "id_format": GRAPH_TAXONOMY["conventions"]["id_format"],
    },
}
