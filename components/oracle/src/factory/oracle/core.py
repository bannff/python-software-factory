"""Core constants for the oracle brick.

The closed neutral verification-state set mirrors the graph brick's
``Finding.state`` field (bd python-factory-216ti Contract B). It is
domain-agnostic: the oracle layers these names ABOVE any per-domain
verdicts and never invents domain-specific states.
"""

from __future__ import annotations

FINDING_STATES: frozenset[str] = frozenset(
    {"candidate", "verifying", "verified", "refuted"}
)

__all__ = ["FINDING_STATES"]
