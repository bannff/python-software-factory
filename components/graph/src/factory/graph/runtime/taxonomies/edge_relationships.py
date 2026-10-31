"""Edge mesh workflow taxonomy — relationship-type definitions.

Pure data mirroring ``can_failure_relationships.py``. Companion to
``edge_nodes.py`` and the top-level ``edge.py`` register entry point.
Vocabulary from ``edge-mesh-workflow-design/design.md`` §2-§3 and
``edge-cases.md`` (C7 verify predicates).

Source / target constraints are narrow where semantics demand it
(EDGE_TRIGGERED_BY, EDGE_JOURNALED) and pipe-delimited where the
spec allows flexibility (EDGE_TARGETS also reaches a device via the
declarative ``payload.target_device`` route).
"""

from __future__ import annotations

EDGE_RELATIONSHIP_TYPES: dict = {
    "EDGE_OBSERVED_ON": {
        "description": (
            "An observation (sensor/model fact) was produced by a mesh "
            "device. Trigger source for workflow proposal (§C1)."
        ),
        "source": "EdgeObservation",
        "target": "EdgeDevice",
        "properties": ["observed_at", "engine_id"],
    },
    "EDGE_TARGETS": {
        "description": (
            "A workflow declaratively routes to a device via "
            "``payload.target_device`` — routing is data, not election. "
            "Target may also be carried by the proposal trigger "
            "(Observation) when routing follows the sensing device."
        ),
        "source": "EdgeWorkflow",
        "target": "EdgeDevice|EdgeObservation",
        "properties": ["target_device", "routed_at"],
    },
    "EDGE_TRIGGERED_BY": {
        "description": (
            "A workflow proposal cites the content-addressed observation "
            "that triggered it (``trigger_id``); the derivation makes "
            "duplicate proposals converge to one workflow doc (§C1)."
        ),
        "source": "EdgeWorkflow",
        "target": "EdgeObservation",
        "properties": ["trigger_id", "created_at"],
    },
    "EDGE_CLAIMED_BY": {
        "description": (
            "A claim is lodged against a device's workflow. Rival claims "
            "coexist as distinct content-addressed docs; winner = lowest "
            "claimant_device_id among unexpired leases (§C2)."
        ),
        "source": "EdgeClaim",
        "target": "EdgeDevice",
        "properties": ["claimed_at", "lease_expires_at", "capability_id"],
    },
    "EDGE_PRODUCED": {
        "description": (
            "A result (or outbox intent doc, outcome='executing') was "
            "produced by the executing device. Multiple results coexist "
            "under takeover; interpreter prefers earliest completed_at (§C4)."
        ),
        "source": "EdgeResult",
        "target": "EdgeDevice",
        "properties": ["outcome", "completed_at"],
    },
    "EDGE_JOURNALED": {
        "description": (
            "A signed transition entry belongs to a workflow's "
            "content-addressed transitions map — the replicated journal "
            "with non-repudiation per entry (§C5, audit-only in v1)."
        ),
        "source": "EdgeTransition",
        "target": "EdgeWorkflow",
        "properties": ["step_no", "step_name", "actor", "transition_id"],
    },
    "EDGE_VERIFY_FOR": {
        "description": (
            "A C7 verify-as-check predicate: an observation (the world's "
            "goal-state fact) verifies a workflow's declared ``verify`` "
            "predicate. Sensor capability gates claim eligibility via "
            "mesh_membership.capabilities; settle-window effects need "
            "re-check (§C7)."
        ),
        "source": "EdgeObservation",
        "target": "EdgeWorkflow",
        "properties": ["predicate", "checked_at", "settle_window_seconds"],
    },
}

__all__ = ["EDGE_RELATIONSHIP_TYPES"]
