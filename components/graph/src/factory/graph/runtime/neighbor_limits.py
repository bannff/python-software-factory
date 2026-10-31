"""Shared resource bounds for Graph neighborhood reads."""
from __future__ import annotations

MAX_NEIGHBOR_LIMIT = 200
DEFAULT_NEIGHBOR_LIMIT = 20


def validate_neighbor_limit(limit: int) -> int:
    """Reject invalid direct-port limits instead of silently widening reads."""
    if type(limit) is not int or not 1 <= limit <= MAX_NEIGHBOR_LIMIT:
        raise ValueError(
            f"neighbor limit must be an integer between 1 and {MAX_NEIGHBOR_LIMIT}"
        )
    return limit


__all__ = ["DEFAULT_NEIGHBOR_LIMIT", "MAX_NEIGHBOR_LIMIT", "validate_neighbor_limit"]
