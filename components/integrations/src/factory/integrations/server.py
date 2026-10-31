"""MCP server factory for integrations brick."""

from __future__ import annotations

from typing import Any

from factory.integrations.runtime.adapters.fake_email import FakeEmailSender
from factory.integrations.runtime.runtime import IntegrationsRuntime
from factory.integrations.runtime.ports import ProtectedArtifactMaterializer
from factory.integrations.mcp import (
    register_authoring,
    register_deterministic,
    register_operational,
    register_provider_email,
    register_prompts,
    register_resources,
    register_views,
)
from factory.mcp_utils.server import make_lazy_runner


def _compose_runtime(
    runtime: IntegrationsRuntime | None,
    materializer: ProtectedArtifactMaterializer | None,
    fake_email_owner: str | None, fake_email_tenant: str | None,
    fake_email_connection_ref: str | None,
) -> IntegrationsRuntime:
    runtime = runtime or IntegrationsRuntime(materializer=materializer)
    values = (fake_email_owner, fake_email_tenant, fake_email_connection_ref)
    if any(value is not None for value in values):
        if materializer is None or not all(values):
            raise ValueError(
                "fake protected email requires materializer, tenant, owner, and connection"
            )
        runtime.register_email_connection(
            fake_email_tenant, fake_email_owner, fake_email_connection_ref, FakeEmailSender(),
        )
    return runtime


def _register_tools(registry: Any, runtime: IntegrationsRuntime) -> None:
    register_deterministic(registry, runtime)
    register_operational(registry, runtime)
    register_provider_email(registry, runtime)
    register_authoring(registry, runtime)
    register_views(registry)


def create_tool_catalog(
    runtime: IntegrationsRuntime | None = None, *,
    materializer: ProtectedArtifactMaterializer | None = None,
    fake_email_owner: str | None = None, fake_email_tenant: str | None = None,
    fake_email_connection_ref: str | None = None,
) -> Any:
    """Create the transport-neutral Integrations tool catalog."""
    from factory.mcp_utils.runtime.tool_catalog import ToolCatalog

    active_runtime = _compose_runtime(
        runtime, materializer, fake_email_owner, fake_email_tenant,
        fake_email_connection_ref,
    )
    catalog = ToolCatalog("integrations-module")
    _register_tools(catalog, active_runtime)
    register_resources(catalog, active_runtime)
    register_prompts(catalog, active_runtime)
    return catalog


def create_mcp_server(
    runtime: IntegrationsRuntime | None = None, *,
    materializer: ProtectedArtifactMaterializer | None = None,
    fake_email_owner: str | None = None, fake_email_tenant: str | None = None,
    fake_email_connection_ref: str | None = None,
) -> Any:
    """Return the canonical framework-neutral catalog."""
    return create_tool_catalog(
        runtime, materializer=materializer,
        fake_email_owner=fake_email_owner, fake_email_tenant=fake_email_tenant,
        fake_email_connection_ref=fake_email_connection_ref,
    )


def get_capabilities() -> dict[str, Any]:
    """Return machine-readable capabilities for integrations brick."""
    return {
        "name": "integrations",
        "version": "1.0.0",
        "backends": ["rest", "graphql", "webhook"],
        "features": ["rest_connector", "graphql_connector", "webhook_receiver", "connection_pooling"],
    }


def health_check() -> dict[str, Any]:
    """Fast readiness probe for integrations brick."""
    return {"healthy": True, "connectors": 0}


def describe_config_schema() -> dict[str, Any]:
    """Describe integrations configuration schema."""
    return {
        "type": "object",
        "properties": {
            "default_timeout": {"type": "integer", "description": "Default request timeout"},
            "max_retries": {"type": "integer", "description": "Max retry attempts"},
        },
    }


get_mcp_server, main = make_lazy_runner(create_mcp_server)

if __name__ == "__main__":
    main()
