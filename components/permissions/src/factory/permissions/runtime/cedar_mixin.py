"""Cedar policy evaluation mixin for PermissionsRuntime."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from .evaluation.cedar import CedarAdapter, CedarEvalRequest

if TYPE_CHECKING:
    from pathlib import Path
    from .models import Settings


class CedarMixin:
    """Mixin providing Cedar policy evaluation capabilities."""

    _cedar: CedarAdapter | None
    _config_dir: "Path"
    _settings: "Settings"

    def _init_cedar(self) -> None:
        """Initialize Cedar adapter if enabled in settings."""
        self._cedar = None
        if self._settings.cedar.enabled:
            cedar_dir = self._config_dir / self._settings.cedar.policies_subdir
            self._cedar = CedarAdapter(cedar_dir)

    def evaluate_cedar(
        self,
        *,
        principal: str,
        action: str,
        resource: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Evaluate using Cedar policies.

        Args:
            principal: Cedar principal (e.g., 'User::"alice"')
            action: Cedar action (e.g., 'Action::"read"')
            resource: Cedar resource (e.g., 'Document::"doc123"')
            context: Optional context dict

        Returns:
            Evaluation result with decision and diagnostics
        """
        if not self._cedar:
            return {
                "decision": "deny",
                "error": "Cedar not enabled. Set cedar.enabled=true in settings.",
            }

        request = CedarEvalRequest(
            principal=principal,
            action=action,
            resource=resource,
            context=context,
        )
        result = self._cedar.evaluate(request)
        return {
            "decision": result.decision,
            "diagnostics": result.diagnostics,
            "determining_policies": result.determining_policies,
        }

    def get_cedar_policies(self) -> list[dict[str, Any]]:
        """Get list of loaded Cedar policies."""
        if not self._cedar:
            return []
        return self._cedar.get_policies()

    def cedar_health(self) -> dict[str, Any]:
        """Get Cedar adapter health status."""
        if not self._cedar:
            return {"enabled": False}
        return self._cedar.health_check()
