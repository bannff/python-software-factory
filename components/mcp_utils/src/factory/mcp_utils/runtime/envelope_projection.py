"""Project trusted envelopes into strict brick-local nested DTO shapes."""
from __future__ import annotations

from typing import Any

_AUTHORITY = {
    "tenant_id", "principal_id", "owner_id", "client_id", "roles", "scopes",
    "producer_id", "visibility", "source_namespace", "agent_id",
}


def project_envelope_arguments(
    handler: Any, arguments: dict[str, Any], ambient: dict[str, Any],
) -> dict[str, Any]:
    """Project declared fields; ambient authority wins and cannot be forged."""
    model = getattr(handler, "_mcp_input_model", None)
    fields = getattr(model, "model_fields", {})
    if "envelope" not in fields:
        if arguments.get("envelope") is not None:
            raise ValueError("caller authority is forbidden")
        return arguments
    root = model.model_json_schema(mode="validation")
    properties = _properties(root, root["properties"]["envelope"])
    if properties is None:
        if arguments.get("envelope") is not None:
            raise ValueError("caller authority is forbidden")
        return arguments
    explicit = arguments.get("envelope")
    explicit = explicit if isinstance(explicit, dict) else {}
    projected: dict[str, Any] = {}
    for key in properties:
        if ambient.get(key) is not None:
            projected[key] = ambient[key]
        elif key not in _AUTHORITY and key in explicit:
            projected[key] = explicit[key]
    return {**arguments, "envelope": projected}


def _properties(
    root: dict[str, Any], schema: dict[str, Any],
) -> dict[str, Any] | None:
    for candidate in schema.get("anyOf", [schema]):
        resolved = candidate
        ref = candidate.get("$ref")
        if isinstance(ref, str) and ref.startswith("#/$defs/"):
            resolved = root.get("$defs", {}).get(ref.rsplit("/", 1)[-1], {})
        if resolved.get("type") == "object" or isinstance(resolved.get("properties"), dict):
            return resolved.get("properties", {})
    return None


__all__ = ["project_envelope_arguments"]
