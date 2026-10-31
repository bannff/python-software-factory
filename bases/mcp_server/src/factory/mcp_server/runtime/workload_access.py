"""Generic gateway enforcement for provider-verified workload principals."""
from __future__ import annotations

import os
from typing import Any

from factory.mcp_utils.interface import AccessOperation, AccessPrincipal

_CONTROL = frozenset({
    "call_brick_tool", "get_brick_prompts", "get_brick_resources",
    "get_brick_tools", "get_capabilities", "get_tool_catalog", "health_check",
    "list_bricks", "read_brick_resource", "render_brick_prompt",
})


def workload_context(
    principal: AccessPrincipal, operation: AccessOperation,
) -> tuple[dict[str, Any], str | None]:
    """Enforce exact verified scope/category without revalidating provider grants."""
    claims = principal.claims
    if claims.get("actor_type") != "workload":
        return {}, None
    if _control(operation):
        return {}, "workload_control_plane_denied"
    allowed = claims.get("allowed_tools")
    scopes = tuple(allowed) if isinstance(allowed, list) else ()
    if not scopes or scopes != principal.scopes or len(scopes) != len(set(scopes)):
        return {}, "workload_binding_denied"
    if operation.public_name not in scopes:
        return {}, "workload_scope_denied"
    expected_audience = os.environ.get("MCP_AUTH_AUDIENCE")
    valid = (
        bool(expected_audience)
        and claims.get("audience") == expected_audience
        and claims.get("tenant_id") == principal.tenant_id
        and claims.get("subject") == principal.subject
        and claims.get("credential_id") == principal.client_id
        and principal.roles == ("workload",)
        and operation.category in {"deterministic", "operational"}
    )
    if not valid:
        return {}, "workload_binding_denied"
    return {
        "actor_type": "workload",
        "workload_launch_id": claims.get("launch_id"),
        "workload_generation": claims.get("generation"),
        "capability_policy_id": claims.get("policy_id"),
        "capability_scope_digest": claims.get("capability_scope_digest"),
        "workload_manifest_digest": claims.get("manifest_digest"),
    }, None


def _control(operation: AccessOperation) -> bool:
    name = operation.public_name.lower().replace(".", "_")
    leaf = operation.source_name.lower().replace(".", "_")
    parts = set(name.split("_"))
    return (
        operation.category not in {"deterministic", "operational"}
        or leaf in _CONTROL
        or name in _CONTROL
        or any(name.endswith(f"_{item}") for item in _CONTROL)
        or leaf.startswith("auth_")
        or bool(parts & {"authoring", "auth", "credential", "token"})
    )


__all__ = ["workload_context"]
