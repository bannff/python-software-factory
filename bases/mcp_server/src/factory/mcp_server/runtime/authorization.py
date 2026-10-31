"""Canonical child-tool policy helpers for progressive MCP surfaces."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any, get_args

from factory.mcp_utils.interface import AccessOperation, get_service

_AUTHORITY_FIELDS = frozenset({
    "tenant_id", "principal_id", "owner_id", "client_id", "roles", "scopes",
    "producer_id", "visibility", "source_namespace", "agent_id",
})


def is_authorized(item: Any, action: str) -> bool:
    controller = get_service("mcp_access_controller")
    if controller is None:
        return True
    principal = controller.principal()
    if principal is None:
        return False
    category = getattr(getattr(item.tool, "fn", None), "_mcp_category", None)
    operation = AccessOperation(
        action=action, public_name=item.public_name, brick=item.brick,
        source_name=item.source_name,
        category=str(category) if category is not None else None,
    )
    return controller.decide(principal, operation).allowed


def is_named_authorized(
    brick: str, name: str, action: str, category: str,
) -> bool:
    controller = get_service("mcp_access_controller")
    if controller is None:
        return True
    principal = controller.principal()
    if principal is None:
        return False
    return controller.decide(principal, AccessOperation(
        action=action, public_name=name, brick=brick,
        source_name=name, category=category,
    )).allowed


def trusted_arguments(tool: Any, arguments: dict[str, Any] | None) -> dict[str, Any] | None:
    values = dict(arguments or {})
    input_model = getattr(getattr(tool, "fn", None), "_mcp_input_model", None)
    model_fields = getattr(input_model, "model_fields", {})
    if "envelope" in model_fields:
        from factory.mcp_utils.interface import get_envelope
        ambient = dict(get_envelope() or {})
        explicit = values.get("envelope")
        explicit = dict(explicit) if isinstance(explicit, Mapping) else {}
        allowed = _nested_model_fields(model_fields["envelope"])
        keys = allowed or set(ambient) | set(explicit)
        projected = {}
        for key in keys:
            if ambient.get(key) is not None:
                projected[key] = ambient[key]
            elif key in explicit and key not in _AUTHORITY_FIELDS:
                projected[key] = explicit[key]
            elif key in ambient:
                projected[key] = None
        values["envelope"] = projected
    elif values.get("envelope") is not None:
        return None
    return values


def _nested_model_fields(field: Any) -> set[str]:
    annotation = getattr(field, "annotation", None)
    for candidate in (annotation, *get_args(annotation)):
        fields = getattr(candidate, "model_fields", None)
        if isinstance(fields, dict):
            return set(fields)
    return set()


def filter_projection(projection: Any, action: str = "discover") -> tuple[Any, ...]:
    return tuple(item for item in projection.admitted if is_authorized(item, action))


__all__ = [
    "filter_projection", "is_authorized", "is_named_authorized",
    "trusted_arguments",
]
