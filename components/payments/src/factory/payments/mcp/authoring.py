"""Authoring-gated, typed MCP tools for Payments."""
from __future__ import annotations

from typing import Any, Callable

from pydantic import SecretStr
from factory.mcp_utils.interface import ToolResult, authoring, ok

from ..authoring import is_authoring_enabled
from ..runtime.registry import ProviderConfig, ProviderType, get_registry
from .contracts.inputs import EmptyInput, RegisterProviderInput, UnregisterProviderInput, UpdateProviderInput
from .contracts.outputs import AuthoringStatusOutput, ProviderMutationOutput


def _disabled() -> ToolResult[ProviderMutationOutput]:
    return ok(ProviderMutationOutput(success=False, error="authoring_disabled"))


def register(mcp: Any, get_authoring_tools: Callable[[], Any]) -> None:
    """Register authoring tools with secret-safe ingress and egress."""

    @mcp.tool()
    @authoring(input_model=EmptyInput, output_model=AuthoringStatusOutput)
    def payments_authoring_get_status() -> ToolResult[AuthoringStatusOutput]:
        status = get_authoring_tools().get_status()
        return ok(AuthoringStatusOutput(enabled=bool(status.get("enabled", False))))

    @mcp.tool()
    @authoring(input_model=RegisterProviderInput, output_model=ProviderMutationOutput)
    def payments_authoring_register_provider(
        name: str, provider_type: str, api_key: SecretStr | None = None, public_key: SecretStr | None = None,
        enabled: bool = True, sandbox: bool = True, options: dict[str, Any] | None = None,
    ) -> ToolResult[ProviderMutationOutput]:
        if not is_authoring_enabled():
            return _disabled()
        try:
            config = ProviderConfig(name=name, provider_type=ProviderType(provider_type),
                api_key=api_key.get_secret_value() if api_key else None,
                public_key=public_key.get_secret_value() if public_key else None,
                enabled=enabled, sandbox=sandbox, options=options or {})
            get_registry().register(config)
        except ValueError as error:
            code = "provider_exists" if "already registered" in str(error) else "provider_invalid"
            return ok(ProviderMutationOutput(success=False, error=code))
        return ok(ProviderMutationOutput(success=True, name=name, provider_type=provider_type))

    @mcp.tool()
    @authoring(input_model=UnregisterProviderInput, output_model=ProviderMutationOutput)
    def payments_authoring_unregister_provider(name: str) -> ToolResult[ProviderMutationOutput]:
        if not is_authoring_enabled():
            return _disabled()
        registry = get_registry()
        if registry.get(name) is None:
            return ok(ProviderMutationOutput(success=False, error="provider_not_found"))
        registry.unregister(name)
        return ok(ProviderMutationOutput(success=True, name=name))

    @mcp.tool()
    @authoring(input_model=UpdateProviderInput, output_model=ProviderMutationOutput)
    def payments_authoring_update_provider(
        name: str, enabled: bool | None = None, sandbox: bool | None = None, api_key: SecretStr | None = None,
    ) -> ToolResult[ProviderMutationOutput]:
        if not is_authoring_enabled():
            return _disabled()
        registry = get_registry()
        config = registry.get(name)
        if config is None:
            return ok(ProviderMutationOutput(success=False, error="provider_not_found"))
        updates = {key: value for key, value in {"enabled": enabled, "sandbox": sandbox}.items() if value is not None}
        if api_key is not None:
            updates["api_key"] = api_key.get_secret_value()
        registry.unregister(name)
        registry.register(config.model_copy(update=updates))
        return ok(ProviderMutationOutput(success=True, name=name, updates=list(updates)))
