"""Strict canonical JSON for durable workflow identities and records."""
from __future__ import annotations

import json
from typing import Any

from factory.mcp_utils.protected_persistence import validate_protected_persistence


def persistence_projection(value: Any) -> Any:
    """Central fail-closed gate for every durable Workflow payload."""
    return validate_protected_persistence(value)


def canonical_json(value: Any) -> str:
    """Return canonical durable JSON after validating protected boundaries."""
    return json.dumps(
        persistence_projection(value), sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False,
    )


def canonical_loads(value: str) -> Any:
    """Parse JSON and reject non-finite constants before recanonicalizing."""
    def reject_constant(token: str) -> None:
        raise ValueError(f"non-finite JSON number: {token}")

    parsed = json.loads(value, parse_constant=reject_constant)
    canonical_json(parsed)
    return parsed
