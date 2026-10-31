"""FastMCP Server interface exposing auth tools.

This module is the public MCP surface. It must not contain domain logic.
All business logic is delegated to the AuthRuntime.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from .authoring import AuthoringManager, authoring_enabled
from .runtime.ports import WorkloadCredentialProvider
from .runtime.runtime import AuthRuntime
from .runtime.workload_credentials import (
    DisabledWorkloadCredentialProvider, LocalOpaqueWorkloadCredentialProvider,
)
from .mcp import deterministic, operational, authoring, resources, prompts
from .mcp import workload as workload_mcp
from .mcp import egress as egress_mcp
from .mcp import enroll as enroll_mcp
from .mcp.views import register as register_views


_WORKLOAD_PROVIDER = LocalOpaqueWorkloadCredentialProvider()
_DISABLED_WORKLOAD_PROVIDER = DisabledWorkloadCredentialProvider()
_CREDENTIAL_BROKER: Any | None = None
_ENROLLMENT_STATE_STORE: Any | None = None


def _default_providers() -> dict[str, Any]:
    """Real HTTP OAuth providers (refresh acquirer + SSRF-pinned egress).

    Safe when unconfigured: an empty client_id makes the acquirer return None
    (no network) until the operator sets the client id + a connection is enrolled.
    """
    import httpx
    from .runtime.adapters.http_token_acquirer import HttpProvider
    client = httpx.Client()
    return {"microsoft": HttpProvider(client), "google": HttpProvider(client)}


def get_credential_broker(injected: Any | None = None) -> Any:
    """Resolve the process-singleton tokenless egress broker."""
    global _CREDENTIAL_BROKER
    if injected is not None:
        return injected
    from factory.mcp_utils.interface import get_service
    configured = get_service("credential_broker")
    if configured is not None:
        return configured
    if _CREDENTIAL_BROKER is None:
        from .runtime.adapters.secret_store_service import ServiceSecretStore
        from .runtime.credential_broker import CredentialBroker
        _CREDENTIAL_BROKER = CredentialBroker(ServiceSecretStore(), _default_providers())
    return _CREDENTIAL_BROKER


def get_enrollment_state_store() -> Any:
    """Process-singleton single-use OAuth enrollment state/PKCE store."""
    global _ENROLLMENT_STATE_STORE
    from factory.mcp_utils.interface import get_service
    configured = get_service("enrollment_state_store")
    if configured is not None:
        return configured
    if _ENROLLMENT_STATE_STORE is None:
        from .runtime.enrollment_state import InMemoryEnrollmentStateStore
        _ENROLLMENT_STATE_STORE = InMemoryEnrollmentStateStore()
    return _ENROLLMENT_STATE_STORE


def get_oauth_code_exchanger() -> Any:
    """Resolve the authorization-code exchanger (real httpx by default)."""
    from factory.mcp_utils.interface import get_service
    configured = get_service("oauth_code_exchanger")
    if configured is not None:
        return configured
    import httpx
    from .runtime.adapters.oauth_code_exchanger import OAuthCodeExchanger
    return OAuthCodeExchanger(httpx.Client())


def get_workload_credential_provider(
    injected: WorkloadCredentialProvider | None = None,
) -> WorkloadCredentialProvider:
    if injected is not None:
        return injected
    from factory.mcp_utils.interface import get_service
    configured = get_service("workload_credential_provider")
    if configured is not None:
        return configured
    explicit_local = os.environ.get(
        "MCP_WORKLOAD_LOCAL_SINGLE_PROCESS", "",
    ).lower() in {"1", "true", "yes"}
    if not explicit_local:
        return _DISABLED_WORKLOAD_PROVIDER
    declared_workers = [
        os.environ[name] for name in ("WEB_CONCURRENCY", "UVICORN_WORKERS")
        if name in os.environ
    ]
    try:
        worker_counts = [int(value) for value in declared_workers]
    except ValueError as exc:
        raise ValueError("workload worker counts must be integers") from exc
    if any(count != 1 for count in worker_counts):
        raise ValueError("local opaque workload credentials require exactly one worker")
    return _WORKLOAD_PROVIDER


def get_runtime(*, workload_credential_provider: WorkloadCredentialProvider | None = None,
                ) -> AuthRuntime:
    """Create a default AuthRuntime from environment / sensible defaults.

    Falls back to in-memory backend when config dir has no settings.yaml.
    """
    config_dir = Path(os.environ.get("AUTH_CONFIG_DIR", "./config"))
    # Ensure minimal config exists so AuthRuntime can initialize
    config_dir.mkdir(parents=True, exist_ok=True)
    settings_path = config_dir / "settings.yaml"
    if not settings_path.exists():
        import yaml
        settings_path.write_text(yaml.safe_dump({
            "service_name": "auth-module",
            "backend": "memory",
        }))
    backends_dir = config_dir / "backends"
    backends_dir.mkdir(parents=True, exist_ok=True)
    memory_backend = backends_dir / "memory.yaml"
    if not memory_backend.exists():
        import yaml
        memory_backend.write_text(yaml.safe_dump({"kind": "memory"}))
    return AuthRuntime(config_dir, workload_credentials=get_workload_credential_provider(
        workload_credential_provider))


def _register_tools(registry: Any, runtime: AuthRuntime) -> None:
    enable_authoring = authoring_enabled(runtime.settings_raw)
    manager = AuthoringManager(runtime.config_dir) if enable_authoring else None
    runtime.set_runtime_flags(authoring_enabled=enable_authoring, running_mode="stdio")
    deterministic.register(registry, runtime)
    operational.register(registry, runtime)
    authoring.register(registry, runtime, manager)
    workload_mcp.register(registry, runtime)
    egress_mcp.register(registry, get_credential_broker)
    enroll_mcp.register(registry, get_enrollment_state_store,
                        get_oauth_code_exchanger, get_credential_broker)
    register_views(registry)


def create_tool_catalog(
    runtime: AuthRuntime | None = None, *,
    workload_credential_provider: WorkloadCredentialProvider | None = None,
) -> Any:
    """Create the transport-neutral Auth tool catalog."""
    from factory.mcp_utils.runtime.tool_catalog import ToolCatalog
    active_runtime = runtime or get_runtime(
        workload_credential_provider=workload_credential_provider)
    catalog = ToolCatalog("auth-module")
    _register_tools(catalog, active_runtime)
    resources.register(catalog, active_runtime)
    prompts.register(catalog, active_runtime)
    return catalog


def create_mcp_server(
    runtime: AuthRuntime | None = None, *,
    workload_credential_provider: WorkloadCredentialProvider | None = None,
) -> Any:
    """Return the canonical framework-neutral catalog."""
    return create_tool_catalog(
        runtime, workload_credential_provider=workload_credential_provider)


def get_capabilities() -> dict[str, Any]:
    """Return machine-readable capabilities for auth brick."""
    return {
        "name": "auth",
        "version": "1.0.0",
        "backends": ["keycloak", "memory"],
        "features": ["authentication", "authorization", "token_management", "token_exchange"],
    }


def health_check() -> dict[str, Any]:
    """Fast readiness probe for auth brick."""
    return {"healthy": True, "provider": "keycloak"}


def describe_config_schema() -> dict[str, Any]:
    """Describe auth configuration schema."""
    return {
        "type": "object",
        "properties": {
            "provider": {"type": "string", "enum": ["keycloak", "memory"]},
            "keycloak_url": {"type": "string", "description": "Keycloak server URL"},
            "realm": {"type": "string", "description": "Keycloak realm"},
        },
    }
