"""CAN failure-prediction taxonomy — registration entry point.

Epic python-factory-can-failure. Implements the ``can_failure`` domain
extension described in ``.github/spec/can-failure-prediction.md`` §2.1 and
``.github/spec/rando.md`` §10.4. This module is the **single import
target** for cross-brick consumers — it re-exports the node / relationship
data and exposes ``register()`` + ``DOMAIN_ID``.

Usage::

    from factory.graph.runtime.taxonomies.can_failure import register
    register()  # one call at process start; idempotent at the process level

    # Or via the public interface:
    from factory.graph.interface import register_can_failure_taxonomy
    register_can_failure_taxonomy()

Splitting rationale: ``can_failure_nodes.py`` and
``can_failure_relationships.py`` keep the data files under 200 LOC;
this file owns the registration call + the conventions dict (the
``entity_id_conventions`` block is derived from the node-type dict to
avoid drift between the two).
"""

from __future__ import annotations

from ..taxonomy_registry import register_extension
from .can_failure_nodes import CAN_FAILURE_NODE_TYPES
from .can_failure_relationships import CAN_FAILURE_RELATIONSHIP_TYPES

DOMAIN_ID: str = "can_failure"
"""Registry slug for the CAN failure-prediction domain."""


def _build_conventions() -> dict:
    """Derive ``entity_id_conventions`` from the node-type dict.

    Single source of truth — never duplicate the id-convention string
    between the node-type spec and the conventions block.
    """
    return {
        "domain": DOMAIN_ID,
        "domain_description": (
            "CAN bus failure prediction domain — vehicles, ECUs, frames, "
            "signals, failure modes, and maintenance events."
        ),
        "taxonomy_version": "1.0.0",
        "id_format": (
            "Kebab-case type-prefixed ids "
            "(e.g. vehicle-V001, frame-V001-T042-1700000000000000000, "
            "dtc-P1234, failure-coolant-coolant_leak)."
        ),
        "timestamps": (
            "Frame timestamps are integer nanoseconds (timestamp_ns). "
            "Episode / maintenance / annotation timestamps are ISO-8601 "
            "strings (start_ts, end_ts, performed_at, annotated_at)."
        ),
        "id_examples": {
            node: spec["id_example"]
            for node, spec in CAN_FAILURE_NODE_TYPES.items()
        },
        "entity_id_conventions": {
            node: spec["id_convention"]
            for node, spec in CAN_FAILURE_NODE_TYPES.items()
        },
        "cross_domain": (
            "The Rando graph brick merges this extension on top of the "
            "security base. The CAN domain is the seed for the Rando "
            "ML dataset generation and agentic label refinement pipelines."
        ),
    }


CAN_FAILURE_CONVENTIONS: dict = _build_conventions()
"""Conventions dict — id formats, timestamp policy, cross-domain notes."""


def register() -> None:
    """Register the ``can_failure`` extension with the taxonomy registry.

    Idempotent only at the **process** level: the underlying
    ``register_extension`` raises ``ValueError`` on collision. Tests that
    call ``taxonomy_registry.reset_extensions()`` must call ``register()``
    again to repopulate the registry for that test case.
    """
    register_extension(
        DOMAIN_ID,
        node_types=CAN_FAILURE_NODE_TYPES,
        relationship_types=CAN_FAILURE_RELATIONSHIP_TYPES,
        conventions=CAN_FAILURE_CONVENTIONS,
    )


__all__ = [
    "DOMAIN_ID",
    "CAN_FAILURE_NODE_TYPES",
    "CAN_FAILURE_RELATIONSHIP_TYPES",
    "CAN_FAILURE_CONVENTIONS",
    "register",
]
