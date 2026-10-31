"""MCP resources for auth module."""

from __future__ import annotations

import json
from typing import Any, TYPE_CHECKING


from .docs import DOCS, get_doc, list_docs
from ..runtime.models import (
    KeycloakBackendConfig,
    Principal,
    TokenIntrospection,
    TokenResponse,
    UserInfo,
)

if TYPE_CHECKING:
    from ..runtime.runtime import AuthRuntime


def register(mcp: Any, runtime: "AuthRuntime") -> None:
    """Register MCP resources for auth."""

    # Schema resources
    @mcp.resource("auth://schemas/keycloak-config")
    def get_keycloak_config_schema() -> str:
        """JSON schema for Keycloak backend configuration."""
        return json.dumps(KeycloakBackendConfig.model_json_schema(), indent=2)

    @mcp.resource("auth://schemas/principal")
    def get_principal_schema() -> str:
        """JSON schema for Principal model."""
        return json.dumps(Principal.model_json_schema(), indent=2)

    @mcp.resource("auth://schemas/token-introspection")
    def get_introspection_schema() -> str:
        """JSON schema for token introspection result."""
        return json.dumps(TokenIntrospection.model_json_schema(), indent=2)

    @mcp.resource("auth://schemas/token-response")
    def get_token_response_schema() -> str:
        """JSON schema for token response."""
        return json.dumps(TokenResponse.model_json_schema(), indent=2)

    @mcp.resource("auth://schemas/user-info")
    def get_user_info_schema() -> str:
        """JSON schema for user info."""
        return json.dumps(UserInfo.model_json_schema(), indent=2)

    # Documentation resources
    @mcp.resource("auth://docs")
    def list_documentation() -> str:
        """List available documentation."""
        return json.dumps({
            "available_docs": list_docs(),
            "access_pattern": "auth://docs/{doc_name}",
        }, indent=2)

    @mcp.resource("auth://docs/overview")
    def get_overview_doc() -> str:
        """Overview documentation."""
        return get_doc("overview") or "Documentation not found"

    @mcp.resource("auth://docs/keycloak")
    def get_keycloak_doc() -> str:
        """Keycloak backend documentation."""
        return get_doc("keycloak") or "Documentation not found"

    @mcp.resource("auth://docs/tokens")
    def get_tokens_doc() -> str:
        """Token operations documentation."""
        return get_doc("tokens") or "Documentation not found"

    @mcp.resource("auth://docs/envelope")
    def get_envelope_doc() -> str:
        """Context envelope documentation."""
        return get_doc("envelope") or "Documentation not found"

    # Live data resources
    @mcp.resource("auth://backends")
    def get_backends_list() -> str:
        """List configured auth backends."""
        backends = runtime.list_backends()
        return json.dumps({
            "backends": backends,
            "count": len(backends),
            "default": runtime.default_backend,
        }, indent=2)

    @mcp.resource("auth://status")
    def get_auth_status() -> str:
        """Get current auth module status."""
        health = runtime.health_check()
        caps = runtime.get_capabilities()
        return json.dumps({
            "health": health,
            "capabilities": caps,
        }, indent=2)

    # Factory cross-reference
    @mcp.resource("auth://factory")
    def get_factory_reference() -> str:
        """Cross-reference to factory foreman."""
        return json.dumps({
            "brick": "auth",
            "namespace": "factory.auth",
            "foreman_tools": [
                "foreman_info",
                "foreman_check",
                "foreman_guardian_check",
            ],
            "related_bricks": [
                {"name": "permissions", "purpose": "Fine-grained access control"},
                {"name": "events", "purpose": "Auth event streaming"},
                {"name": "telemetry", "purpose": "Auth metrics and tracing"},
            ],
        }, indent=2)
