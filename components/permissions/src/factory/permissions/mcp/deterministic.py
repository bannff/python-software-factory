"""Strict typed deterministic tools for the Permissions brick."""
from __future__ import annotations

from typing import TYPE_CHECKING

from typing import Any

from factory.mcp_utils.interface import ToolResult, deterministic, ok
from factory.mcp_utils.registration import typed_tool

from .contracts import (
    CapabilitiesOutput,
    ConfigSchemaOutput,
    EmptyInput,
    HealthOutput,
    PolicyRegistryOutput,
    PolicySummary,
    RoleRegistryOutput,
    RoleSummary,
    ToolCatalog,
)

if TYPE_CHECKING:
    from factory.permissions.runtime.runtime import PermissionsRuntime

_AUTHORING_TOOLS = [
    "permissions.authoring.get_status",
    "permissions.authoring.validate_policies",
    "permissions.authoring.upsert_policy",
    "permissions.authoring.delete_policy",
]


def _capabilities(runtime: "PermissionsRuntime", authoring_enabled: bool) -> CapabilitiesOutput:
    raw = runtime.get_capabilities()
    tools = raw.get("tools", {})
    catalog = ToolCatalog(
        deterministic=tools.get("deterministic", []),
        operational=tools.get("operational", []),
        authoring=_AUTHORING_TOOLS if authoring_enabled else [],
    )
    return CapabilitiesOutput(
        schema_version=raw.get("schema_version", 1),
        tools=catalog,
        cedar_enabled=raw.get("cedar_enabled", False),
    )


def register(
    mcp: Any,
    runtime: "PermissionsRuntime",
    *,
    authoring_enabled: bool = False,
) -> None:
    """Register the five deterministic tools with strict flat ingress."""

    @typed_tool(mcp, name="permissions.get_capabilities")
    @deterministic(input_model=EmptyInput, output_model=CapabilitiesOutput)
    def get_capabilities() -> ToolResult[CapabilitiesOutput]:
        """Get the live Permissions tool catalog and backend capabilities."""
        return ok(_capabilities(runtime, authoring_enabled))

    @typed_tool(mcp, name="permissions.health_check")
    @deterministic(input_model=EmptyInput, output_model=HealthOutput)
    def health_check() -> ToolResult[HealthOutput]:
        """Return a safe readiness projection for the Permissions runtime."""
        return ok(HealthOutput(
            status="healthy",
            policies_loaded=len(runtime.get_policies()),
            roles_loaded=len(runtime.get_role_registry()),
        ))

    @typed_tool(mcp, name="permissions.describe_config_schema")
    @deterministic(input_model=EmptyInput, output_model=ConfigSchemaOutput)
    def describe_config_schema() -> ToolResult[ConfigSchemaOutput]:
        """Return bounded JSON schemas for settings and policies."""
        from factory.permissions.runtime.models import PolicyDefinition, Settings

        return ok(ConfigSchemaOutput(
            settings=Settings.model_json_schema(),
            policy=PolicyDefinition.model_json_schema(),
        ))

    @typed_tool(mcp, name="permissions.get_role_registry")
    @deterministic(input_model=EmptyInput, output_model=RoleRegistryOutput)
    def get_role_registry() -> ToolResult[RoleRegistryOutput]:
        """List registered roles through a typed projection."""
        roles = [RoleSummary.model_validate(item) for item in runtime.get_role_registry()]
        return ok(RoleRegistryOutput(roles=roles, count=len(roles)))

    @typed_tool(mcp, name="permissions.get_policy_registry")
    @deterministic(input_model=EmptyInput, output_model=PolicyRegistryOutput)
    def get_policy_registry() -> ToolResult[PolicyRegistryOutput]:
        """List loaded policy metadata without returning policy contents."""
        policies = [
            PolicySummary(
                id=policy.id,
                name=policy.name,
                version=policy.version,
                tags=policy.tags,
                rules_count=len(policy.rules),
            )
            for policy in runtime.get_policies()
        ]
        return ok(PolicyRegistryOutput(policies=policies, count=len(policies)))


__all__ = ["register"]
