"""Edge mesh workflow taxonomy — registration entry point.

Companion-X edge doctrine (Orchestrator v2 / Edge section): edge
artifacts are DATA — the vocabulary of the mesh-workflow design
(``projects/companion_x/experiments/edge_models/edge-mesh-workflow-design/``,
schema v1: workflows / claims / results / mesh_membership collections,
content-addressed ids, derived task state) as a first-class taxonomy.
This module is the **single import target** for cross-brick consumers —
it re-exports the node / relationship data and exposes ``register()`` +
``DOMAIN_ID``.

Usage::

    from factory.graph.runtime.taxonomies.edge import register
    register()  # one call at process start

    # Or via the public interface:
    from factory.graph.interface import register_edge_taxonomy
    register_edge_taxonomy()

Splitting rationale mirrors ``can_failure``: ``edge_nodes.py`` and
``edge_relationships.py`` keep the data files under 200 LOC; this file
owns the registration call + the conventions dict (the
``entity_id_conventions`` block is derived from the node-type dict to
avoid drift between the two).
"""

from __future__ import annotations

from ..taxonomy_registry import register_extension
from .edge_nodes import EDGE_NODE_TYPES
from .edge_relationships import EDGE_RELATIONSHIP_TYPES

DOMAIN_ID: str = "edge"
"""Registry slug for the edge mesh-workflow domain."""


def _build_conventions() -> dict:
    """Derive ``entity_id_conventions`` from the node-type dict.

    Single source of truth — never duplicate the id-convention string
    between the node-type spec and the conventions block.
    """
    return {
        "domain": DOMAIN_ID,
        "domain_description": (
            "Edge mesh workflow coordination — devices, workflow "
            "instances, claims, results, signed transition journals, and "
            "the observations that trigger workflows. All state is "
            "derived by every peer from CRDT-merged documents; ids are "
            "content-addressed (sha256) per design.md §2."
        ),
        "taxonomy_version": "1.0.0",
        "id_format": (
            "Content-addressed ids per edge-cases.md §C1 and design.md: "
            "wf_<sha256(target_device + action + blueprint_version + "
            "trigger_id)[:24]>, claim-<sha256(workflow_id + "
            "claimant_device_id)>, result-<sha256(workflow_id + claim_id "
            "+ outcome)>, transition-<sha256(workflow_id + step_no + "
            "step_name + actor_key)[:32]>, obs-<sha256(canonical_json({"
            "device_id, input_id_sha256, model_sha256}))>. Same-id / "
            "different-content is an integrity error (read-back compare), "
            "never silent LWW."
        ),
        "timestamps": (
            "Integer epoch seconds per design.md §2 (claimed_at, "
            "lease_expires_at, completed_at, created_at, "
            "last_heartbeat_at). Timestamps are self-declared, not proof "
            "(mesh-coordinator-001 clock-trust caveat); lease validity is "
            "evaluated against each peer's own clock at read time."
        ),
        "id_examples": {
            node: spec["id_example"]
            for node, spec in EDGE_NODE_TYPES.items()
        },
        "entity_id_conventions": {
            node: spec["id_convention"]
            for node, spec in EDGE_NODE_TYPES.items()
        },
        "epistemic_status": (
            "Optional property on every edge node type: "
            "harness-proven (simulated-merge matrix V1-V10), sdk-live "
            "(gated on the internal offline license), convention (peer "
            "agreement, no runtime enforcement), q1-gap (needs Q1'27 "
            "DQL-native functions: effect compensation, on-peer signature "
            "verification, declarative lease expiry)."
        ),
        "cross_domain": (
            "Derived task state (PROPOSED → CLAIMED → EXECUTING → "
            "COMPLETED/FAILED) is never stored — every peer's observer "
            "loop recomputes it from merged documents. Fork at a "
            "one-of step marks the workflow BLOCKED_FORK (fail-safe, "
            "never guess). Physical actions fire only behind outbox "
            "intent docs with idempotency keys."
        ),
    }


EDGE_CONVENTIONS: dict = _build_conventions()
"""Conventions dict — id formats, timestamp policy, cross-domain notes."""


def register() -> None:
    """Register the ``edge`` extension with the taxonomy registry.

    Idempotent only at the **process** level: the underlying
    ``register_extension`` raises ``ValueError`` on collision. Tests that
    call ``taxonomy_registry.reset_extensions()`` must call ``register()``
    again to repopulate the registry for that test case.
    """
    register_extension(
        DOMAIN_ID,
        node_types=EDGE_NODE_TYPES,
        relationship_types=EDGE_RELATIONSHIP_TYPES,
        conventions=EDGE_CONVENTIONS,
    )


__all__ = [
    "DOMAIN_ID",
    "EDGE_NODE_TYPES",
    "EDGE_RELATIONSHIP_TYPES",
    "EDGE_CONVENTIONS",
    "register",
]
