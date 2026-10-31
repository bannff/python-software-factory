"""Edge mesh workflow taxonomy — node definitions.

Pure data mirroring ``can_failure_nodes.py``. Vocabulary from
``projects/companion_x/experiments/edge_models/edge-mesh-workflow-design/design.md``
§2 (collections: workflows / claims / results / mesh_membership, plus the
transition journal map) and the device-flow observation schema
(``edge-ditto-device-flow-001/contracts.py::observation_document``).

``epistemic_status`` is an optional property convention carried on every
node type: ``harness-proven`` (simulated-merge harness V1-V10),
``sdk-live`` (gated on the internal offline license), ``convention`` (peer
agreement, no runtime enforcement), ``q1-gap`` (needs Q1'27 DQL-native
functions).
"""

from __future__ import annotations

EDGE_NODE_TYPES: dict = {
    "EdgeDevice": {
        "description": (
            "A mesh member device (``mesh_membership`` doc, one per "
            "device, self-written only). Anchor for EDGE_TARGETS, "
            "EDGE_OBSERVED_ON, EDGE_CLAIMED_BY, EDGE_PRODUCED."
        ),
        "required_properties": ["device_id", "pub_key", "schema_version"],
        "optional_properties": [
            "capabilities", "last_heartbeat_at", "epistemic_status",
        ],
        "id_convention": "device-<device_id>",
        "id_example": "device-pump-04",
    },
    "EdgeWorkflow": {
        "description": (
            "One workflow instance (``workflows`` doc, creator-written, "
            "INSERT-only). Carries the payload↔registry contract: "
            "blueprint_version, min_runtime_version, required_primitives "
            "declared in payload; host validates before activation. "
            "Duplicate proposals converge to one doc via ON ID CONFLICT "
            "DO NOTHING (edge-cases.md §C1)."
        ),
        "required_properties": [
            "workflow_id", "blueprint_version", "min_runtime_version",
            "payload", "payload_sha256", "target_device", "schema_version",
            "created_at",
        ],
        "optional_properties": [
            "required_primitives", "trigger_id", "verify", "settle_window_seconds",
            "epistemic_status",
        ],
        "id_convention": (
            "wf_<sha256(target_device + action + blueprint_version + "
            "trigger_id)[:24]>"
        ),
        "id_example": "wf_3f2a9c8e1b7d4a6e0f5c2b8d",
    },
    "EdgeClaim": {
        "description": (
            "A task claim (``claims`` doc, content-addressed per "
            "(workflow, claimant) so rival claims coexist; winner = "
            "lowest claimant_device_id among unexpired leases — §C2). "
            "Lease ``lease_expires_at`` is an LWW register renewed by the "
            "claimant only; expiry is observer-evaluated clock math (§C3)."
        ),
        "required_properties": [
            "workflow_id", "claimant_device_id", "claim_key_pub",
            "claimed_at", "capability_id", "min_runtime_ok",
            "lease_expires_at",
        ],
        "optional_properties": ["epistemic_status"],
        "id_convention": "claim-<sha256(workflow_id + claimant_device_id)>",
        "id_example": (
            "claim-9d1f0a3b7c2e5d4806a1f3e9b2c7d40581ea6c3fb9d20714e5a8c3f60b2d91e4"
        ),
    },
    "EdgeResult": {
        "description": (
            "Append-only execution evidence (``results`` doc, "
            "content-addressed per (workflow, claim, outcome); takeover "
            "writes a distinct doc, interpreter prefers earliest "
            "completed_at, tie-broken by lowest _id). Also the outbox "
            "intent doc form: outcome='executing' gates the physical "
            "action (§C4)."
        ),
        "required_properties": [
            "workflow_id", "claim_id", "executor_device_id",
            "started_transition_id", "outcome", "completed_at",
        ],
        "optional_properties": ["output", "action_key", "epistemic_status"],
        "id_convention": (
            "result-<sha256(workflow_id + claim_id + outcome)>"
        ),
        "id_example": (
            "result-4e8c2b6d0f1a9375c8e2d6b4a0f3c19d7e5b2a8d4c6f0e2a8b4d6f0c2a4e6d80"
        ),
    },
    "EdgeTransition": {
        "description": (
            "One journal entry in the workflow's ``transitions`` MAP "
            "(never an array — map keys merge cleanly under concurrent "
            "appends; the v0→v1 structural correction). Content-addressed "
            "key; same-key/different-content = integrity error. "
            "Signatures are audit-only provenance in v1 (no on-peer "
            "verification — flagged q1-gap, §C5)."
        ),
        "required_properties": [
            "workflow_id", "step_no", "step_name", "actor", "timestamp",
        ],
        "optional_properties": ["signature", "epistemic_status"],
        "id_convention": (
            "transition-<sha256(workflow_id + step_no + step_name + "
            "actor_key)[:32]>"
        ),
        "id_example": "transition-3f2a9c8e1b7d4a6e0f5c2b8d4e6a0c2e",
    },
    "EdgeObservation": {
        "description": (
            "The sensor/model fact that triggers workflows — mirrors the "
            "edge-ditto-device-flow-001 observation document "
            "(probability + decision per engine, content-addressed id). "
            "Also the C7 verify-as-check anchor: the world IS a shared "
            "CRDT; a goal-state check is a query over observations."
        ),
        "required_properties": [
            "device_id", "input_id_sha256", "model_sha256", "model_kind",
            "probability", "decision", "schema_version",
        ],
        "optional_properties": [
            "scenario_id", "engine_id", "cohort_sha256",
            "epistemic_status",
        ],
        "id_convention": (
            "obs-<sha256(canonical_json({device_id, input_id_sha256, "
            "model_sha256}))>"
        ),
        "id_example": (
            "obs-7c1e9a3f5b2d8064c2e8a0b4d6f2c8e0a4b6d8f0c2e4a6b8d0f2c4e6a8b0d2f4"
        ),
    },
}

__all__ = ["EDGE_NODE_TYPES"]
