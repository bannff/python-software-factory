"""Bounded canonical JSON for opaque Workflow material."""
from __future__ import annotations

from typing import Any

from factory.mcp_utils.interface import is_bounded_json, to_plain_json

from .canonical import canonical_json, canonical_loads


def bounded_canonical(value: Any) -> tuple[dict[str, Any], str]:
    """Return a bounded JSON object and its canonical representation."""
    plain = to_plain_json(value)
    if not isinstance(plain, dict) or not is_bounded_json(plain):
        raise ValueError("execution material must be a bounded JSON object")
    encoded = canonical_json(plain)
    return canonical_loads(encoded), encoded


__all__ = ["bounded_canonical"]
