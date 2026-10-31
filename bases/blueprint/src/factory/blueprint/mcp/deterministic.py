"""Typed deterministic MCP tools for Blueprint service discovery and IaC validation."""
from __future__ import annotations

from typing import Callable

from typing import Any
from factory.mcp_utils.interface import ToolResult, deterministic

from .deterministic_contracts import (
    CapabilitiesOutput, ConfigSchemaOutput, EmptyInput, GetServiceUrlInput,
    GetServiceUrlOutput, HealthOutput, ListServicesOutput, SupportedServicesOutput,
    ValidateSpecsInput, ValidateSpecsOutput,
)
from ..core import SERVICE_CDK_MODULES
from ..runtime.normalizer import normalize_spec
from ..runtime.resolver import resolve
from ..runtime.runtime import BlueprintRuntime


def register(mcp: Any, get_runtime: Callable[[], BlueprintRuntime]) -> None:
    """Register deterministic tools with strict public contracts."""

    @mcp.tool(name="blueprint_get_capabilities")
    @deterministic(input_model=EmptyInput, output_model=CapabilitiesOutput)
    def blueprint_get_capabilities() -> ToolResult[CapabilitiesOutput]:
        return {"name": "blueprint", "version": "2.0.0", "type": "base",
                "backends": BlueprintRuntime.available_backends(),
                "features": ["service_discovery", "infrastructure_config", "cdk_generation",
                             "pipeline_generation"], "services": get_runtime().list_services()}

    @mcp.tool(name="blueprint_health_check")
    @deterministic(input_model=EmptyInput, output_model=HealthOutput)
    def blueprint_health_check() -> ToolResult[HealthOutput]:
        health = get_runtime().health_check()
        return {"healthy": all(item.healthy for item in health.values()), "services": {
            name: {"healthy": item.healthy, "url": item.url} for name, item in health.items()}}

    @mcp.tool(name="blueprint_describe_config_schema")
    @deterministic(input_model=EmptyInput, output_model=ConfigSchemaOutput)
    def blueprint_describe_config_schema() -> ToolResult[ConfigSchemaOutput]:
        return {"type": "object", "properties": {
            "FACTORY_POSTGRES_URL": {"type": "string"},
            "FACTORY_NEO4J_URL": {"type": "string"},
            "FACTORY_REDIS_URL": {"type": "string"},
            "FACTORY_KEYCLOAK_URL": {"type": "string"},
            "FACTORY_SEAWEED_URL": {"type": "string"},
            "FACTORY_CHROMA_HOST": {"type": "string"},
            "FACTORY_CHROMA_PORT": {"type": "integer"},
            "FACTORY_CELERY_BROKER_URL": {"type": "string"},
            "FACTORY_DAGSTER_URL": {"type": "string"},
            "FACTORY_PHOENIX_URL": {"type": "string"}}}

    @mcp.tool(name="blueprint_get_service_url")
    @deterministic(input_model=GetServiceUrlInput, output_model=GetServiceUrlOutput)
    def blueprint_get_service_url(service_name: str) -> ToolResult[GetServiceUrlOutput]:
        url = get_runtime().get_service_url(service_name)
        return {"found": True, "service": service_name, "url": url} if url else {
            "found": False, "service": service_name, "error": "Service not found"}

    @mcp.tool(name="blueprint_list_services")
    @deterministic(input_model=EmptyInput, output_model=ListServicesOutput)
    def blueprint_list_services() -> ToolResult[ListServicesOutput]:
        runtime = get_runtime()
        return {"services": runtime.list_services(), "urls": runtime.get_all_urls()}

    @mcp.tool(name="blueprint_list_supported_services")
    @deterministic(input_model=EmptyInput, output_model=SupportedServicesOutput)
    def blueprint_list_supported_services() -> ToolResult[SupportedServicesOutput]:
        return {"services": {service: {"module": module, "construct": construct,
                "alias": alias} for service, (module, construct, alias) in SERVICE_CDK_MODULES.items()}}

    @mcp.tool(name="blueprint_validate_specs")
    @deterministic(input_model=ValidateSpecsInput, output_model=ValidateSpecsOutput)
    def blueprint_validate_specs(specs: list[dict]) -> ToolResult[ValidateSpecsOutput]:
        from ..runtime.renderers.cdk import CdkRenderer

        resources = []
        for spec in specs:
            resources.extend(normalize_spec(spec.get("brick", "unknown"), spec.get("spec", spec)))
        blueprint = resolve(resources)
        errors = CdkRenderer().validate(blueprint)
        return {"valid": not errors, "resource_count": len(resources),
                "services_used": sorted(blueprint.services_used),
                "vpc_required": blueprint.vpc_required, "errors": errors}
