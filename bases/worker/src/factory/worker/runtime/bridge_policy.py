"""Principal-aware default-deny policy for the Worker MCP bridge."""
from __future__ import annotations

import os
from dataclasses import dataclass, field

from factory.mcp_utils.interface import get_principal_id


@dataclass(frozen=True)
class BridgeDecision:
    """Stable public decision for one bridge capability check."""

    allowed: bool
    code: str | None = None


@dataclass(frozen=True)
class BridgePolicy:
    """Exact tool allowlist with an explicit privileged-principal gate."""

    allowlist: frozenset[str] = field(default_factory=frozenset)
    privileged_principals: frozenset[str] = field(default_factory=frozenset)
    dangerous_tools: frozenset[str] = field(default_factory=frozenset)

    @classmethod
    def from_env(cls) -> "BridgePolicy":
        """Build a policy from process configuration; unset means deny all."""
        allowlist = os.environ.get(
            "FACTORY_WORKER_BRIDGE_ALLOWLIST",
            os.environ.get("FACTORY_WORKER_BRIDGE_ALLOWED_TOOLS", ""),
        )
        privileged = os.environ.get("FACTORY_WORKER_BRIDGE_PRIVILEGED_PRINCIPALS", "")
        dangerous = os.environ.get("FACTORY_WORKER_BRIDGE_DANGEROUS_TOOLS", "")
        return cls(
            allowlist=_csv(allowlist),
            privileged_principals=_csv(privileged),
            dangerous_tools=_csv(dangerous),
        )

    @property
    def allowed_tools(self) -> frozenset[str]:
        """Compatibility alias for callers that use an ``allowed_tools`` name."""
        return self.allowlist

    def decide(
        self,
        tool_name: str,
        principal_id: str | None = None,
        *,
        category: str | None = None,
    ) -> BridgeDecision:
        """Return the same capability decision used by listing and execution."""
        if tool_name not in self.allowlist:
            return BridgeDecision(False, "bridge_access_denied")
        principal = principal_id if principal_id is not None else get_principal_id()
        if self._is_dangerous(tool_name, category) and principal not in self.privileged_principals:
            return BridgeDecision(False, "bridge_access_denied")
        return BridgeDecision(True)

    def _is_dangerous(self, tool_name: str, category: str | None = None) -> bool:
        return (
            category in {"operational", "authoring"}
            or tool_name in self.dangerous_tools
            or ".authoring." in tool_name
            or tool_name.startswith("authoring.")
            or "_authoring_" in tool_name
        )


def _csv(value: str) -> frozenset[str]:
    return frozenset(item.strip() for item in value.split(",") if item.strip())


def resolve_principal(principal_id: str | None = None) -> str | None:
    """Resolve an explicit compatibility principal or request context principal."""
    return principal_id if principal_id is not None else get_principal_id()


__all__ = ["BridgeDecision", "BridgePolicy", "resolve_principal"]
