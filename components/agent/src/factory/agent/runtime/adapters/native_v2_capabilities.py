"""Agent-owned construction of the framework-neutral native MCP-v2 client."""
from __future__ import annotations

from factory.mcp_utils.interface import (
    CapabilityScope,
    NativeV2ScopedCapabilityClient,
    ScopedCapabilityClientPort,
)


def create_native_v2_capability_client(
    server: object,
    scope: CapabilityScope,
) -> ScopedCapabilityClientPort:
    """Bind canonical trusted authority to the native MCP-v2 server."""
    trusted = CapabilityScope.create(
        scope.policy_id, scope.tool_names,
        delegation_depth=scope.delegation_depth, digest=scope.digest,
    )
    return NativeV2ScopedCapabilityClient(server, trusted)


__all__ = ["create_native_v2_capability_client"]
