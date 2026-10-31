"""Public, transport-neutral policy-decision composition."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol


class DecisionPointPort(Protocol):
    def decide(
        self, *, action: str, resource: dict[str, Any], context: dict[str, Any],
        principal_id: str, tenant_id: str | None,
    ) -> dict[str, Any]: ...


@dataclass(frozen=True, slots=True)
class RuntimeDecisionPoint:
    runtime: Any

    def decide(
        self, *, action: str, resource: dict[str, Any], context: dict[str, Any],
        principal_id: str, tenant_id: str | None,
    ) -> dict[str, Any]:
        from .runtime.envelope import Envelope

        return self.runtime.evaluate(
            action=action, resource=resource, context=context,
            envelope=Envelope(principal_id=principal_id, tenant_id=tenant_id),
        )


def create_decision_point(*, local_mode: bool = False) -> DecisionPointPort:
    """Build the configured YAML decision point; missing policy fails closed."""
    from .runtime.runtime import PermissionsRuntime

    configured = os.environ.get("MCP_PERMISSIONS_CONFIG_DIR")
    if not configured:
        if not local_mode:
            raise ValueError("MCP_PERMISSIONS_CONFIG_DIR is required")
        configured = str(Path(__file__).parents[5] / "config" / "mcp_permissions")
    runtime = PermissionsRuntime(configured)
    if not runtime.get_policies():
        raise ValueError("MCP permissions policy set is empty")
    return RuntimeDecisionPoint(runtime)


__all__ = ["DecisionPointPort", "create_decision_point"]
