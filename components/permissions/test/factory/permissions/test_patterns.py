"""Tests for pattern matching."""
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


class TestPatternMatching:
    """Test action and resource pattern matching."""

    def test_wildcard_action(self, tmp_path: Path) -> None:
        """Wildcard * should match any action."""
        _write_config_with_policy(tmp_path, [{
            "id": "r1",
            "effect": "allow",
            "actions": ["*"],
            "resource_types": ["doc"],
        }])
        runtime = PermissionsRuntime.from_config_dir(tmp_path)
        
        for action in ["read", "write", "delete", "anything"]:
            result = runtime.evaluate(
                action=action,
                resource={"type": "doc"},
                context={},
                envelope=Envelope(),
            )
            assert result["decision"] == "allow", f"Failed for action: {action}"

    def test_prefix_pattern(self, tmp_path: Path) -> None:
        """Prefix pattern should match actions starting with prefix."""
        _write_config_with_policy(tmp_path, [{
            "id": "r1",
            "effect": "allow",
            "actions": ["read*"],
            "resource_types": ["doc"],
        }])
        runtime = PermissionsRuntime.from_config_dir(tmp_path)
        
        # Match
        for action in ["read", "read:all", "read:metadata"]:
            result = runtime.evaluate(
                action=action,
                resource={"type": "doc"},
                context={},
                envelope=Envelope(),
            )
            assert result["decision"] == "allow", f"Should match: {action}"
        
        # No match
        result = runtime.evaluate(
            action="write",
            resource={"type": "doc"},
            context={},
            envelope=Envelope(),
        )
        assert result["decision"] == "deny"

    def test_multiple_actions(self, tmp_path: Path) -> None:
        """Multiple actions should match any."""
        _write_config_with_policy(tmp_path, [{
            "id": "r1",
            "effect": "allow",
            "actions": ["read", "list", "describe"],
            "resource_types": ["doc"],
        }])
        runtime = PermissionsRuntime.from_config_dir(tmp_path)
        
        for action in ["read", "list", "describe"]:
            result = runtime.evaluate(
                action=action,
                resource={"type": "doc"},
                context={},
                envelope=Envelope(),
            )
            assert result["decision"] == "allow"
        
        result = runtime.evaluate(
            action="delete",
            resource={"type": "doc"},
            context={},
            envelope=Envelope(),
        )
        assert result["decision"] == "deny"

    def test_resource_id_pattern(self, tmp_path: Path) -> None:
        """Resource ID patterns should match."""
        _write_config_with_policy(tmp_path, [{
            "id": "r1",
            "effect": "allow",
            "actions": ["read"],
            "resource_types": ["doc"],
            "resource_ids": ["public-*"],
        }])
        runtime = PermissionsRuntime.from_config_dir(tmp_path)
        
        # Match
        result = runtime.evaluate(
            action="read",
            resource={"type": "doc", "id": "public-123"},
            context={},
            envelope=Envelope(),
        )
        assert result["decision"] == "allow"
        
        # No match
        result = runtime.evaluate(
            action="read",
            resource={"type": "doc", "id": "private-456"},
            context={},
            envelope=Envelope(),
        )
        assert result["decision"] == "deny"
