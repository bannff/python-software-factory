"""Tests for condition operators."""
from __future__ import annotations

from pathlib import Path

import yaml

from factory.permissions.runtime.envelope import Envelope
from factory.permissions.runtime.runtime import PermissionsRuntime


def _write_config_with_policy(cfg: Path, rules: list) -> None:
    (cfg / "policies").mkdir(parents=True, exist_ok=True)
    (cfg / "settings.yaml").write_text(yaml.safe_dump({
        "schema_version": 1,
        "service_name": "test",
        "backend": "filesystem",
        "authoring": {"enabled": False},
        "policy_store": {"policies_subdir": "policies"},
    }))
    (cfg / "policies" / "test.yaml").write_text(yaml.safe_dump({
        "schema_version": 1,
        "id": "test",
        "name": "Test Policy",
        "version": "1.0",
        "rules": rules,
    }))


class TestConditionOperators:
    """Test all condition operators."""

    def test_eq_operator(self, tmp_path: Path) -> None:
        """Test equality operator."""
        _write_config_with_policy(tmp_path, [{
            "id": "r1",
            "effect": "allow",
            "actions": ["read"],
            "resource_types": ["doc"],
            "conditions": [{"key": "resource.visibility", "op": "eq", "value": "public"}],
        }])
        runtime = PermissionsRuntime.from_config_dir(tmp_path)
        
        # Match
        result = runtime.evaluate(
            action="read",
            resource={"type": "doc", "visibility": "public"},
            context={},
            envelope=Envelope(),
        )
        assert result["decision"] == "allow"
        
        # No match
        result = runtime.evaluate(
            action="read",
            resource={"type": "doc", "visibility": "private"},
            context={},
            envelope=Envelope(),
        )
        assert result["decision"] == "deny"

    def test_ne_operator(self, tmp_path: Path) -> None:
        """Test not-equal operator."""
        _write_config_with_policy(tmp_path, [{
            "id": "r1",
            "effect": "allow",
            "actions": ["read"],
            "resource_types": ["doc"],
            "conditions": [{"key": "resource.visibility", "op": "ne", "value": "private"}],
        }])
        runtime = PermissionsRuntime.from_config_dir(tmp_path)
        
        # Match (public != private)
        result = runtime.evaluate(
            action="read",
            resource={"type": "doc", "visibility": "public"},
            context={},
            envelope=Envelope(),
        )
        assert result["decision"] == "allow"
        
        # No match (private == private)
        result = runtime.evaluate(
            action="read",
            resource={"type": "doc", "visibility": "private"},
            context={},
            envelope=Envelope(),
        )
        assert result["decision"] == "deny"

    def test_in_operator(self, tmp_path: Path) -> None:
        """Test in-list operator."""
        _write_config_with_policy(tmp_path, [{
            "id": "r1",
            "effect": "allow",
            "actions": ["read"],
            "resource_types": ["doc"],
            "conditions": [{"key": "resource.visibility", "op": "in", "value": ["public", "team"]}],
        }])
        runtime = PermissionsRuntime.from_config_dir(tmp_path)
        
        # Match
        result = runtime.evaluate(
            action="read",
            resource={"type": "doc", "visibility": "team"},
            context={},
            envelope=Envelope(),
        )
        assert result["decision"] == "allow"
        
        # No match
        result = runtime.evaluate(
            action="read",
            resource={"type": "doc", "visibility": "private"},
            context={},
            envelope=Envelope(),
        )
        assert result["decision"] == "deny"

    def test_contains_operator_list(self, tmp_path: Path) -> None:
        """Test contains operator with list."""
        _write_config_with_policy(tmp_path, [{
            "id": "r1",
            "effect": "allow",
            "actions": ["read"],
            "resource_types": ["doc"],
            "conditions": [{"key": "context.tags", "op": "contains", "value": "featured"}],
        }])
        runtime = PermissionsRuntime.from_config_dir(tmp_path)
        
        # Match
        result = runtime.evaluate(
            action="read",
            resource={"type": "doc"},
            context={"tags": ["featured", "popular"]},
            envelope=Envelope(),
        )
        assert result["decision"] == "allow"
        
        # No match
        result = runtime.evaluate(
            action="read",
            resource={"type": "doc"},
            context={"tags": ["draft"]},
            envelope=Envelope(),
        )
        assert result["decision"] == "deny"

    def test_exists_operator(self, tmp_path: Path) -> None:
        """Test exists operator."""
        _write_config_with_policy(tmp_path, [{
            "id": "r1",
            "effect": "allow",
            "actions": ["read"],
            "resource_types": ["doc"],
            "conditions": [{"key": "context.user_id", "op": "exists"}],
        }])
        runtime = PermissionsRuntime.from_config_dir(tmp_path)
        
        # Match
        result = runtime.evaluate(
            action="read",
            resource={"type": "doc"},
            context={"user_id": "u123"},
            envelope=Envelope(),
        )
        assert result["decision"] == "allow"
        
        # No match
        result = runtime.evaluate(
            action="read",
            resource={"type": "doc"},
            context={},
            envelope=Envelope(),
        )
        assert result["decision"] == "deny"
