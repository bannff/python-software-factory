"""Tests for role-based access control."""
from __future__ import annotations

from pathlib import Path

import yaml

from factory.permissions.runtime.envelope import Envelope
from factory.permissions.runtime.runtime import PermissionsRuntime


def _write_config_with_roles(cfg: Path) -> None:
    """Create config with roles."""
    (cfg / "policies").mkdir(parents=True, exist_ok=True)
    (cfg / "roles").mkdir(parents=True, exist_ok=True)
    
    (cfg / "settings.yaml").write_text(yaml.safe_dump({
        "schema_version": 1,
        "service_name": "test",
        "backend": "filesystem",
        "authoring": {"enabled": False},
        "policy_store": {"policies_subdir": "policies"},
    }))
    
    # Define roles
    (cfg / "roles" / "admin.yaml").write_text(yaml.safe_dump({
        "id": "admin",
        "name": "Administrator",
        "permissions": ["*"],
    }))
    
    (cfg / "roles" / "editor.yaml").write_text(yaml.safe_dump({
        "id": "editor",
        "name": "Editor",
        "permissions": ["read", "write", "update"],
    }))
    
    (cfg / "roles" / "viewer.yaml").write_text(yaml.safe_dump({
        "id": "viewer",
        "name": "Viewer",
        "permissions": ["read"],
    }))
    
    # Policy using roles
    (cfg / "policies" / "rbac.yaml").write_text(yaml.safe_dump({
        "schema_version": 1,
        "id": "rbac-policy",
        "name": "Role-Based Policy",
        "version": "1.0",
        "rules": [
            {
                "id": "admin-all",
                "effect": "allow",
                "actions": ["*"],
                "resource_types": ["*"],
                "conditions": [
                    {"key": "context.roles", "op": "contains", "value": "admin"}
                ],
            },
            {
                "id": "editor-write",
                "effect": "allow",
                "actions": ["read", "write", "update"],
                "resource_types": ["document"],
                "conditions": [
                    {"key": "context.roles", "op": "contains", "value": "editor"}
                ],
            },
            {
                "id": "viewer-read",
                "effect": "allow",
                "actions": ["read"],
                "resource_types": ["document"],
                "conditions": [
                    {"key": "context.roles", "op": "contains", "value": "viewer"}
                ],
            },
        ],
    }))


class TestRoleBasedAccess:
    """Test role-based access control."""

    def test_admin_can_do_anything(self, tmp_path: Path) -> None:
        """Admin role should allow all actions."""
        _write_config_with_roles(tmp_path)
        runtime = PermissionsRuntime.from_config_dir(tmp_path)
        
        result = runtime.evaluate(
            action="delete",
            resource={"type": "document", "id": "doc-1"},
            context={"roles": ["admin"]},
            envelope=Envelope(),
        )
        
        assert result["decision"] == "allow"

    def test_editor_can_write(self, tmp_path: Path) -> None:
        """Editor role should allow write actions."""
        _write_config_with_roles(tmp_path)
        runtime = PermissionsRuntime.from_config_dir(tmp_path)
        
        result = runtime.evaluate(
            action="write",
            resource={"type": "document", "id": "doc-1"},
            context={"roles": ["editor"]},
            envelope=Envelope(),
        )
        
        assert result["decision"] == "allow"

    def test_editor_cannot_delete(self, tmp_path: Path) -> None:
        """Editor role should not allow delete."""
        _write_config_with_roles(tmp_path)
        runtime = PermissionsRuntime.from_config_dir(tmp_path)
        
        result = runtime.evaluate(
            action="delete",
            resource={"type": "document", "id": "doc-1"},
            context={"roles": ["editor"]},
            envelope=Envelope(),
        )
        
        assert result["decision"] == "deny"

    def test_viewer_can_only_read(self, tmp_path: Path) -> None:
        """Viewer role should only allow read."""
        _write_config_with_roles(tmp_path)
        runtime = PermissionsRuntime.from_config_dir(tmp_path)
        
        # Can read
        result = runtime.evaluate(
            action="read",
            resource={"type": "document", "id": "doc-1"},
            context={"roles": ["viewer"]},
            envelope=Envelope(),
        )
        assert result["decision"] == "allow"
        
        # Cannot write
        result = runtime.evaluate(
            action="write",
            resource={"type": "document", "id": "doc-1"},
            context={"roles": ["viewer"]},
            envelope=Envelope(),
        )
        assert result["decision"] == "deny"

    def test_no_role_denied(self, tmp_path: Path) -> None:
        """No role should deny access."""
        _write_config_with_roles(tmp_path)
        runtime = PermissionsRuntime.from_config_dir(tmp_path)
        
        result = runtime.evaluate(
            action="read",
            resource={"type": "document", "id": "doc-1"},
            context={"roles": []},
            envelope=Envelope(),
        )
        
        assert result["decision"] == "deny"

    def test_get_role_registry(self, tmp_path: Path) -> None:
        """Should return list of defined roles."""
        _write_config_with_roles(tmp_path)
        runtime = PermissionsRuntime.from_config_dir(tmp_path)
        
        roles = runtime.get_role_registry()
        
        assert len(roles) == 3
        ids = [r["id"] for r in roles]
        assert "admin" in ids
        assert "editor" in ids
        assert "viewer" in ids
