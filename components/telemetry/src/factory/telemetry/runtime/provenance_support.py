"""Authentication and canonical identity helpers for Telemetry provenance."""
from __future__ import annotations

import hashlib
import json
from typing import Any

from pydantic import ValidationError

from factory.mcp_utils.interface import get_envelope

from .provenance_models import AuthenticatedTelemetryContext


class ProvenanceAuthenticationError(ValueError):
    """The server did not bind a complete authenticated Telemetry context."""


def authenticated_context(
    envelope: dict[str, Any] | None = None,
) -> AuthenticatedTelemetryContext:
    """Resolve and validate the server-bound context, never caller payload data."""
    raw = envelope if envelope is not None else get_envelope()
    if not isinstance(raw, dict):
        raise ProvenanceAuthenticationError("unauthenticated_context")
    try:
        return AuthenticatedTelemetryContext.model_validate(raw)
    except ValidationError as exc:
        raise ProvenanceAuthenticationError("unauthenticated_context") from exc


def fingerprint(value: Any) -> str:
    """Return the canonical replay fingerprint for a JSON-compatible value."""
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode()).hexdigest()


def telemetry_ref(context: AuthenticatedTelemetryContext, source_id: str) -> str:
    """Derive a stable reference scoped to the authenticated producer."""
    return "telemetry:" + fingerprint({
        "tenant_id": context.tenant_id,
        "producer_id": context.producer_id,
        "source_id": source_id,
    })


__all__ = ["ProvenanceAuthenticationError", "authenticated_context", "fingerprint", "telemetry_ref"]
