"""Role definitions and registry."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class RoleDefinition(BaseModel):
    """A role definition."""
    id: str = Field(min_length=1, max_length=128)
    name: str = Field(min_length=1, max_length=256)
    description: str = ""
    permissions: list[str] = Field(default_factory=list)
    inherits: list[str] = Field(default_factory=list)  # Role inheritance


class RoleRegistry:
    """Registry for role definitions loaded from config."""

    def __init__(self, config_dir: Path):
        self.config_dir = Path(config_dir)
        self.roles: dict[str, RoleDefinition] = {}
        self._load_roles()

    def _load_roles(self) -> None:
        """Load roles from config/roles/*.yaml."""
        roles_dir = self.config_dir / "roles"
        if not roles_dir.exists():
            return

        for path in roles_dir.glob("*.yaml"):
            try:
                data = yaml.safe_load(path.read_text())
                if data:
                    role = RoleDefinition.model_validate(data)
                    self.roles[role.id] = role
            except Exception:
                # Skip invalid files
                pass

    def get(self, role_id: str) -> RoleDefinition | None:
        """Get role by ID."""
        return self.roles.get(role_id)

    def get_permissions(self, role_id: str) -> set[str]:
        """Get all permissions for a role, including inherited."""
        role = self.roles.get(role_id)
        if not role:
            return set()
        
        permissions = set(role.permissions)
        
        # Add inherited permissions
        for inherited_id in role.inherits:
            permissions.update(self.get_permissions(inherited_id))
        
        return permissions

    def as_list(self) -> list[dict[str, Any]]:
        """Return list of role metadata."""
        return [
            {
                "id": r.id,
                "name": r.name,
                "description": r.description,
                "permissions": r.permissions,
                "inherits": r.inherits,
            }
            for r in self.roles.values()
        ]
