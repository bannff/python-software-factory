"""CloudFormation stack + service-mock operations for the sandbox runtime.

These operations all delegate to the adapter's ``execute`` seam (or the
adapter's own mock support) and carry no lifecycle state of their own, so they
live here as a mixin to keep ``runtime.py`` focused on environment lifecycle.
"""
from __future__ import annotations

from typing import Any, Protocol

from .ports import SandboxPort


class _HasAdapter(Protocol):
    _adapter: SandboxPort


class CfnStackOpsMixin:
    """CFN stack + service-mock methods, mixed into ``SandboxRuntime``."""

    async def deploy_stack(
        self: _HasAdapter, env_id: str, stack_name: str, template_body: str,
        parameters: dict[str, Any] | None = None,
        capabilities: list[str] | None = None,
    ) -> dict[str, Any]:
        """Deploy a CFN stack to the sandbox environment."""
        from .adapters.cfn_ops import deploy_stack
        return await deploy_stack(
            self._adapter.execute, env_id, stack_name,
            template_body, parameters, capabilities)

    async def list_stacks(self: _HasAdapter, env_id: str) -> dict[str, Any]:
        """List CFN stacks in the sandbox environment."""
        from .adapters.cfn_ops import list_stacks
        return await list_stacks(self._adapter.execute, env_id)

    async def describe_stack(
        self: _HasAdapter, env_id: str, stack_name: str,
    ) -> dict[str, Any]:
        """Describe a CFN stack in the sandbox environment."""
        from .adapters.cfn_ops import describe_stack
        return await describe_stack(self._adapter.execute, env_id, stack_name)

    async def delete_stack(
        self: _HasAdapter, env_id: str, stack_name: str,
    ) -> dict[str, Any]:
        """Delete a CFN stack from the sandbox environment."""
        from .adapters.cfn_ops import delete_stack
        return await delete_stack(self._adapter.execute, env_id, stack_name)

    async def apply_service_mocks(
        self: _HasAdapter, env_id: str, config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Apply service mock configuration to a sandbox environment."""
        if config is None:
            return {"env_id": env_id, "mocks_applied": []}
        from .models import ServiceMockConfig
        mock_config = ServiceMockConfig.model_validate(config)
        if not hasattr(self._adapter, "apply_service_mocks"):
            return {"env_id": env_id, "error": "Adapter does not support service mocks"}
        return await self._adapter.apply_service_mocks(env_id, mock_config)
