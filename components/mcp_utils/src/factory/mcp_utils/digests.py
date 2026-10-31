"""Shared request-digest helper for the tokenless credential-egress path.

Lives in mcp_utils so both the auth broker/egress tool AND the integrations
capability adapter compute the SAME digest without importing each other
(tenet: no cross-brick imports). Uses the shared canonical-JSON encoder so the
bytes are identical on both sides.
"""
from __future__ import annotations

import hashlib

from .protected_content import canonical_json


def egress_request_digest(provider_id: str, route_id: str, connection_ref: str,
                          payload: dict) -> str:
    """Canonical sha256 over the exact egress request identity + payload."""
    return hashlib.sha256(canonical_json({
        "provider_id": provider_id, "route_id": route_id,
        "connection_ref": connection_ref, "payload": payload,
    })).hexdigest()


__all__ = ["egress_request_digest"]
