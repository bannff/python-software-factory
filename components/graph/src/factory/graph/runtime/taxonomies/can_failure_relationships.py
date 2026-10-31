"""CAN failure-prediction taxonomy — relationship-type definitions.

Context extension to the CAN failure taxonomy.
Companion to ``can_failure_nodes.py`` and
the top-level ``can_failure.py`` register entry point. Pure data;
relationship shapes mirror ``mcp/docs_taxonomy_ext.py::EXT_RELATIONSHIP_TYPES``
so the same code can walk any domain's relationship schema.

Source / target constraints are intentionally narrow (one node type
per endpoint) where the semantics demand it (HAS_ECU, EMITS_FRAME,
PART_OF_TRIP) and pipe-delimited where the spec allows flexibility
(CORRELATES_WITH, PRECEDES_FAILURE — both Signal endpoints, but the
target FailureMode may also be reachable from a Frame). Callers that
want strict validation can split on ``"|"`` and check membership.
"""

from __future__ import annotations

CAN_FAILURE_RELATIONSHIP_TYPES: dict = {
    "HAS_ECU": {
        "description": "Vehicle hosts an ECU on a given bus.",
        "source": "Vehicle",
        "target": "ECU",
        "properties": ["installed_at", "bus_name"],
    },
    "PART_OF_TRIP": {
        "description": "A frame belongs to a trip's episode window.",
        "source": "Frame",
        "target": "Trip",
        "properties": ["assigned_at"],
    },
    "EMITS_FRAME": {
        "description": "An ECU transmitted a frame on a bus.",
        "source": "ECU",
        "target": "Frame",
        "properties": ["bus_name", "captured_at_ns"],
    },
    "DEFINES_SIGNAL": {
        "description": "A pinned DBC version canonically defines a signal layout.",
        "source": "DBCVersion",
        "target": "Signal",
        "properties": [],
    },
    "DECODES_TO": {
        "description": (
            "A frame (or arbitration_id) decodes to a physical signal "
            "under a given DBC version. Pivots on (arbitration_id, "
            "dbc_version) for decode-drift detection."
        ),
        "source": "Frame",
        "target": "Signal",
        "properties": ["dbc_version", "decode_at_ns"],
    },
    "CORRELATES_WITH": {
        "description": (
            "Statistical or domain correlation between two signals "
            "(e.g. coolant_temp ↔ fan_rpm). Used by weak-supervision "
            "label expansion."
        ),
        "source": "Signal",
        "target": "Signal",
        "properties": [
            "method", "score", "window_seconds", "computed_at",
        ],
    },
    "PRECEDES_FAILURE": {
        "description": (
            "A signal pattern preceded an observed FailureMode within "
            "a prediction horizon. The core supervision edge for "
            "time-to-failure / failure-within-horizon targets."
        ),
        "source": "Signal",
        "target": "FailureMode",
        "properties": [
            "lead_time_minutes", "horizon_minutes", "confidence",
            "support_count", "observed_at",
        ],
    },
    "REPAIRED_BY": {
        "description": (
            "A failure mode (or its observed DTC) was resolved by a "
            "maintenance event. Ground-truth outcome for the loop."
        ),
        "source": "FailureMode",
        "target": "MaintenanceEvent",
        "properties": ["resolved_at", "technician", "parts_replaced"],
    },
    "ANNOTATED_AS": {
        "description": (
            "A frame (or trip) carries an annotation pointing at a "
            "taxonomy concept (DTC, FailureMode, label). The provenance "
            "edge for agentic label validation."
        ),
        "source": "Frame",
        "target": "DTC",
        "properties": [
            "label_source", "confidence", "annotator",
            "annotated_at", "taxonomy_version",
        ],
    },
    # --- Context extension (bd:python-factory-ctx1) -------------------------
    "OCCURS_DURING": {
        "description": "A frame's timestamp falls within a weather observation's validity window; attaches atmospheric context at the frame level.",
        "source": "Frame",
        "target": "WeatherSnapshot",
        "properties": ["matched_at", "interpolation_method", "confidence"],
    },
    "LOCATED_AT": {
        "description": "A frame's decoded GPS coordinate (or interpolated value) is anchored to a Location node.",
        "source": "Frame",
        "target": "Location",
        "properties": ["captured_at_ns", "gps_source", "accuracy_m"],
    },
    "TRAVERSES": {
        "description": "A trip's path matches a known Route or was used to compute one; trip-level geographic anchor.",
        "source": "Trip",
        "target": "Route",
        "properties": ["computed_at", "match_score", "gps_trace_hash"],
    },
    "HAS_CONTEXT": {
        "description": "A trip is annotated with EnvironmentalContext slices that capture its operational state (weather, location, driving, vehicle).",
        "source": "Trip",
        "target": "EnvironmentalContext",
        "properties": ["window_start_ts", "window_end_ts", "context_role"],
    },
    "INFLUENCES": {
        "description": "An EnvironmentalContext slice statistically correlates with elevated FailureMode incidence; the contextual-supervision edge complementing PRECEDES_FAILURE.",
        "source": "EnvironmentalContext",
        "target": "FailureMode",
        "properties": ["correlation_score", "sample_count", "method", "observed_at"],
    },
}

__all__ = ["CAN_FAILURE_RELATIONSHIP_TYPES"]
