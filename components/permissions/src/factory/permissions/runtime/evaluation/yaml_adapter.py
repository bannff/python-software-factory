"""YAML policy evaluator adapter — implements PolicyEvaluator Protocol.

Wraps the existing ``evaluate_policies`` / ``explain_policies`` functions
so the runtime can swap evaluators via configuration.
"""

from __future__ import annotations

from typing import Any

from factory.permissions.runtime.envelope import Envelope
from factory.permissions.runtime.models import PolicyDefinition, Resource

from .evaluator import evaluate_policies, explain_policies


class YamlEvaluatorAdapter:
    """Built-in YAML policy evaluator behind the PolicyEvaluator port."""

    def __init__(self, policies: list[PolicyDefinition]) -> None:
        self._policies = policies

    def reload(self, policies: list[PolicyDefinition]) -> None:
        self._policies = policies

    def evaluate(
        self,
        *,
        action: str,
        resource: dict[str, Any],
        context: dict[str, Any],
        principal_id: str | None = None,
        tenant_id: str | None = None,
    ) -> dict[str, Any]:
        resource_obj = Resource.model_validate(resource)
        envelope = Envelope(principal_id=principal_id, tenant_id=tenant_id)

        decision, reason, match = evaluate_policies(
            policies=self._policies,
            action=action,
            resource=resource_obj,
            context=context,
            envelope=envelope,
        )

        out: dict[str, Any] = {"decision": decision, "reason": reason}
        if match:
            out["policy_id"] = match.policy_id
            out["rule_id"] = match.rule_id
            if match.obligations:
                out["obligations"] = match.obligations
        return out

    def explain(
        self,
        *,
        action: str,
        resource: dict[str, Any],
        context: dict[str, Any],
        principal_id: str | None = None,
        tenant_id: str | None = None,
    ) -> dict[str, Any]:
        resource_obj = Resource.model_validate(resource)
        envelope = Envelope(principal_id=principal_id, tenant_id=tenant_id)
        return explain_policies(
            policies=self._policies,
            action=action,
            resource=resource_obj,
            context=context,
            envelope=envelope,
        )

    def health_check(self) -> dict[str, Any]:
        return {
            "healthy": True,
            "backend": "yaml",
            "policy_count": len(self._policies),
        }
