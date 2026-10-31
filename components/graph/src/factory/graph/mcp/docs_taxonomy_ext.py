"""Extended graph taxonomy — CWE, OCSF, Games, and Metrics additions.

Extends GRAPH_TAXONOMY with node types and relationship types for:
- CWE Taxonomy (CWECategory)
- OCSF Event Schema (OCSFEventClass, OCSFCategory)
- Games brick (GameSession, GameMove)
- Metrics brick (Baseline)
Imported and merged by docs_taxonomy.py.
"""

EXT_NODE_TYPES: dict = {
    "CWECategory": {
        "description": (
            "OWASP/CWE reference node. Seeded via security_seed_cwe_taxonomy."
        ),
        "required_properties": ["cwe_id", "name", "description", "created_at"],
        "optional_properties": ["parent_cwe"],
        "id_convention": "cwe-{numeric_id}",
        "id_example": "cwe-79",
    },
    "OCSFEventClass": {
        "description": (
            "OCSF v1.3 event class. Seeded via security_seed_ocsf_taxonomy."
        ),
        "required_properties": [
            "class_uid", "class_name", "category_uid", "category_name",
            "description", "created_at",
        ],
        "optional_properties": [],
        "id_convention": "ocsf-class-{class_uid}",
        "id_example": "ocsf-class-2001",
    },
    "OCSFCategory": {
        "description": "OCSF v1.3 top-level category (7 total).",
        "required_properties": [
            "category_uid", "category_name", "description", "created_at",
        ],
        "optional_properties": [],
        "id_convention": "ocsf-cat-{category_uid}",
        "id_example": "ocsf-cat-5",
    },
    "GameSession": {
        "description": (
            "One completed game session. Created by game_pipeline._store_transcript."
        ),
        "required_properties": ["game_type", "created_at"],
        "optional_properties": ["winner", "move_count", "reward", "config"],
        "id_convention": "game-{game_id}",
        "id_example": "game-tictactoe-7f3a",
    },
    "GameMove": {
        "description": "Individual move within a game session.",
        "required_properties": ["step", "action", "created_at"],
        "optional_properties": ["command", "path", "flag", "ts"],
        "id_convention": "move-{game_id}-{step}",
        "id_example": "move-tictactoe-7f3a-0",
    },
    "Baseline": {
        "description": "Named baseline for regression gating (metrics brick).",
        "required_properties": ["metric_id", "tag", "values", "created_at"],
        "optional_properties": [],
        "id_convention": "baseline-{metric_id}-{tag}",
        "id_example": "baseline-f1-v1.0",
    },
}

EXT_RELATIONSHIP_TYPES: dict = {
    # CWE
    "CLASSIFIED_AS": {
        "description": "Finding or SecurityAction classified under a CWE category.",
        "source": "Finding | SecurityAction",
        "target": "CWECategory",
        "properties": ["created_at"],
    },
    "CHILD_OF": {
        "description": "CWE hierarchy — child category points to parent.",
        "source": "CWECategory",
        "target": "CWECategory",
        "properties": [],
    },
    # OCSF
    "CONFORMS_TO": {
        "description": "SecurityAction or Finding conforms to an OCSF event class.",
        "source": "SecurityAction | Finding",
        "target": "OCSFEventClass",
        "properties": ["created_at"],
    },
    "BELONGS_TO": {
        "description": "OCSF event class belongs to an OCSF category.",
        "source": "OCSFEventClass",
        "target": "OCSFCategory",
        "properties": [],
    },
    # Games
    "HAS_MOVE": {
        "description": "Game session contains an individual move (ordered by step).",
        "source": "GameSession",
        "target": "GameMove",
        "properties": [],
    },
    # Metrics
    "BASELINE_OF": {
        "description": "Baseline anchored to a MetricDefinition.",
        "source": "Baseline",
        "target": "MetricDefinition",
        "properties": [],
    },
    "COMPARED_TO": {
        "description": "Snapshot compared against a baseline for regression gating.",
        "source": "Snapshot",
        "target": "Baseline",
        "properties": [
            "signal", "delta_pct", "threshold_block", "threshold_warn", "compared_at",
        ],
    },
}

EXT_ENTITY_ID_CONVENTIONS: dict = {
    "CWECategory": "cwe-{numeric_id}",
    "OCSFEventClass": "ocsf-class-{class_uid}",
    "OCSFCategory": "ocsf-cat-{category_uid}",
    "GameSession": "game-{game_id}",
    "GameMove": "move-{game_id}-{step}",
    "Baseline": "baseline-{metric_id}-{tag}",
}
