"""Tests for Cedar policy evaluation adapter."""

from __future__ import annotations

import pytest
from pathlib import Path
from tempfile import TemporaryDirectory

from factory.permissions.runtime.evaluation.cedar import (
    CedarAdapter,
    CedarEvalRequest,
    CedarPolicy,
)


class TestCedarAdapter:
    """Tests for Cedar adapter."""

    def test_create_adapter(self) -> None:
        """Test creating a Cedar adapter."""
        adapter = CedarAdapter()
        assert adapter.get_policies() == []

    def test_load_policy(self) -> None:
        """Test loading a policy from string."""
        adapter = CedarAdapter()
        adapter.load_policy(
            policy_id="test",
            content='permit(principal, action, resource);',
            source="test.cedar",
        )

        policies = adapter.get_policies()
        assert len(policies) == 1
        assert policies[0]["id"] == "test"

    def test_load_schema(self) -> None:
        """Test loading a schema."""
        adapter = CedarAdapter()
        adapter.load_schema(
            content='{}',
            source="test.cedarschema",
        )

        health = adapter.health_check()
        assert health["has_schema"] is True

    def test_health_check_without_cedarpy(self) -> None:
        """Test health check when cedarpy is not installed."""
        adapter = CedarAdapter()

        health = adapter.health_check()
        # cedarpy may or may not be installed
        assert "cedarpy_available" in health
        assert "policy_count" in health

    def test_evaluate_without_cedarpy(self) -> None:
        """Test evaluation falls back gracefully without cedarpy."""
        adapter = CedarAdapter()
        adapter.load_policy("test", 'permit(principal, action, resource);')

        request = CedarEvalRequest(
            principal='User::"alice"',
            action='Action::"read"',
            resource='Document::"doc1"',
        )

        result = adapter.evaluate(request)
        # Should either work (if cedarpy installed) or return deny with diagnostic
        assert result.decision in ["allow", "deny"]

    def test_load_from_directory(self) -> None:
        """Test loading policies from directory."""
        with TemporaryDirectory() as tmpdir:
            policies_dir = Path(tmpdir)

            # Create a .cedar file
            (policies_dir / "policy1.cedar").write_text(
                'permit(principal, action, resource);'
            )

            adapter = CedarAdapter(policies_dir)
            policies = adapter.get_policies()

            assert len(policies) == 1
            assert policies[0]["id"] == "policy1"

    def test_load_from_nonexistent_directory(self) -> None:
        """Test loading from nonexistent directory doesn't fail."""
        adapter = CedarAdapter(Path("/nonexistent/path"))
        assert adapter.get_policies() == []


class TestCedarEvalRequest:
    """Tests for Cedar evaluation request."""

    def test_create_request(self) -> None:
        """Test creating an evaluation request."""
        request = CedarEvalRequest(
            principal='User::"alice"',
            action='Action::"read"',
            resource='Document::"doc1"',
            context={"ip": "192.168.1.1"},
        )

        assert request.principal == 'User::"alice"'
        assert request.action == 'Action::"read"'
        assert request.resource == 'Document::"doc1"'
        assert request.context == {"ip": "192.168.1.1"}

    def test_request_without_context(self) -> None:
        """Test request without context."""
        request = CedarEvalRequest(
            principal='User::"bob"',
            action='Action::"write"',
            resource='File::"file1"',
        )

        assert request.context is None
