"""Tests for PolicyEvaluator adapters (YamlEvaluatorAdapter).

Exercises the adapter through the PolicyEvaluator Protocol interface.
"""

from __future__ import annotations

import pytest

from factory.permissions.runtime.evaluation.yaml_adapter import YamlEvaluatorAdapter
from factory.permissions.runtime.models import PolicyDefinition, Rule


@pytest.fixture
def policies() -> list[PolicyDefinition]:
    """Simple allow/deny policy set."""
    return [
        PolicyDefinition(
            id="p1",
            name="Allow read",
            rules=[
                Rule(
                    id="r1",
                    effect="allow",
                    actions=["read"],
                    resource_types=["document"],
                ),
            ],
        ),
        PolicyDefinition(
            id="p2",
            name="Deny delete",
            rules=[
                Rule(
                    id="r2",
                    effect="deny",
                    actions=["delete"],
                    resource_types=["document"],
                ),
            ],
        ),
    ]


@pytest.fixture
def evaluator(policies: list[PolicyDefinition]) -> YamlEvaluatorAdapter:
    return YamlEvaluatorAdapter(policies)


class TestYamlEvaluatorAdapter:
    """Tests for YamlEvaluatorAdapter through PolicyEvaluator Protocol."""

    def test_import(self) -> None:
        """Adapter is importable."""
        assert YamlEvaluatorAdapter is not None

    def test_evaluate_allow(self, evaluator: YamlEvaluatorAdapter) -> None:
        """Allowed action returns allow decision."""
        result = evaluator.evaluate(
            action="read",
            resource={"type": "document", "id": "doc-1"},
            context={},
        )
        assert result["decision"] == "allow"

    def test_evaluate_deny(self, evaluator: YamlEvaluatorAdapter) -> None:
        """Denied action returns deny decision."""
        result = evaluator.evaluate(
            action="delete",
            resource={"type": "document", "id": "doc-1"},
            context={},
        )
        assert result["decision"] == "deny"

    def test_evaluate_default_deny(self, evaluator: YamlEvaluatorAdapter) -> None:
        """Unmatched action defaults to deny."""
        result = evaluator.evaluate(
            action="admin_nuke",
            resource={"type": "document", "id": "doc-1"},
            context={},
        )
        assert result["decision"] == "deny"

    def test_explain_returns_trace(self, evaluator: YamlEvaluatorAdapter) -> None:
        """explain() returns decision with trace info."""
        result = evaluator.explain(
            action="read",
            resource={"type": "document", "id": "doc-1"},
            context={},
        )
        assert "decision" in result or "trace" in result or "matched_rules" in result

    def test_health_check(self, evaluator: YamlEvaluatorAdapter) -> None:
        """health_check reports healthy with policy count."""
        health = evaluator.health_check()
        assert health["healthy"] is True
        assert health["backend"] == "yaml"
        assert health["policy_count"] == 2

    def test_reload_policies(self, evaluator: YamlEvaluatorAdapter) -> None:
        """reload() updates the policy set."""
        evaluator.reload([])
        health = evaluator.health_check()
        assert health["policy_count"] == 0

    def test_with_principal_and_tenant(self, evaluator: YamlEvaluatorAdapter) -> None:
        """evaluate() accepts principal_id and tenant_id."""
        result = evaluator.evaluate(
            action="read",
            resource={"type": "document", "id": "doc-1"},
            context={},
            principal_id="user-42",
            tenant_id="tenant-a",
        )
        assert "decision" in result
