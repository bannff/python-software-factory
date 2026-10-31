"""Ports (Protocol interfaces) for the permissions brick.

Adapters implement these Protocols so the runtime stays backend-agnostic.
"""

from __future__ import annotations

from typing import Any, Protocol

from factory.permissions.runtime.models import PolicyDefinition


class PolicyStore(Protocol):
    """Port: loads policy definitions from a backend (filesystem, DB, etc.)."""

    def load_policies(self) -> list[PolicyDefinition]:
        ...

    def health_check(self) -> dict[str, object]:
        ...


class PolicyEvaluator(Protocol):
    """Port: evaluates an access-control request against loaded policies.

    Implementations include the built-in YAML evaluator and the Cedar
    adapter.  The runtime selects one based on configuration.
    """

    def evaluate(
        self,
        *,
        action: str,
        resource: dict[str, Any],
        context: dict[str, Any],
        principal_id: str | None = None,
        tenant_id: str | None = None,
    ) -> dict[str, Any]:
        """Return ``{"decision": "allow"|"deny", ...}``."""
        ...

    def explain(
        self,
        *,
        action: str,
        resource: dict[str, Any],
        context: dict[str, Any],
        principal_id: str | None = None,
        tenant_id: str | None = None,
    ) -> dict[str, Any]:
        """Return decision plus a trace of matched rules."""
        ...

    def health_check(self) -> dict[str, Any]:
        ...
