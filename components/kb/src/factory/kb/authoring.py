"""Security-gated authoring tools for knowledge base module."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from .runtime.collections import CollectionConfig


class KBAuthoring:
    """Security-gated authoring tools for knowledge base collections.
    
    Authoring tools are disabled by default and must be explicitly
    enabled via the KB_ENABLE_AUTHORING_TOOLS environment variable.
    
    All file operations are strictly scoped to config_dir with
    path traversal protection.
    """

    def __init__(self, config_dir: str | Path) -> None:
        self._config_dir = Path(config_dir).resolve()
        self._collections_dir = self._config_dir / "collections"

    def is_enabled(self) -> bool:
        """Check if authoring tools are enabled."""
        return os.environ.get("KB_ENABLE_AUTHORING_TOOLS", "").lower() in (
            "1", "true", "yes"
        )

    def _validate_path(self, name: str) -> tuple[bool, str | Path]:
        """Validate that a path is safe and within config_dir."""
        # Reject absolute paths
        if name.startswith("/") or name.startswith("\\"):
            return False, "Absolute paths are not allowed"
        
        # Reject path traversal
        if ".." in name:
            return False, "Path traversal is not allowed"
        
        # Construct and validate final path
        target = (self._collections_dir / f"{name}.yaml").resolve()
        
        # Ensure it's within config_dir
        try:
            target.relative_to(self._config_dir)
        except ValueError:
            return False, "Path is outside config directory"
        
        return True, target

    def get_status(self) -> dict[str, Any]:
        """Get authoring tools status."""
        return {
            "enabled": self.is_enabled(),
            "config_dir": str(self._config_dir),
            "collections_dir": str(self._collections_dir),
            "env_var": "KB_ENABLE_AUTHORING_TOOLS",
        }

    def validate_collections(self, dry_run: bool = True) -> dict[str, Any]:
        """Validate all collection configurations."""
        if not self.is_enabled():
            return {"ok": False, "error": "Authoring tools are disabled"}
        
        errors = []
        valid_count = 0
        
        if self._collections_dir.exists():
            for config_file in self._collections_dir.glob("*.yaml"):
                try:
                    with open(config_file) as f:
                        data = yaml.safe_load(f)
                    if data:
                        CollectionConfig.model_validate(data)
                        valid_count += 1
                except ValidationError as e:
                    errors.append({
                        "file": config_file.name,
                        "errors": e.errors(),
                    })
                except Exception as e:
                    errors.append({
                        "file": config_file.name,
                        "errors": str(e),
                    })
        
        return {
            "ok": len(errors) == 0,
            "valid": valid_count,
            "errors": errors,
        }

    def upsert_collection_config(
        self,
        collection_id: str,
        data: dict[str, Any],
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Create or update a collection configuration."""
        if not self.is_enabled():
            return {"ok": False, "error": "Authoring tools are disabled"}
        
        # Validate path
        valid, result = self._validate_path(collection_id)
        if not valid:
            return {"ok": False, "error": result}
        
        target_path = result
        
        # Validate data
        try:
            config = CollectionConfig.model_validate(data)
        except ValidationError as e:
            return {"ok": False, "error": "Validation failed", "details": e.errors()}
        
        if dry_run:
            return {"ok": True, "dry_run": True, "would_write": str(target_path)}
        
        # Write file
        self._collections_dir.mkdir(parents=True, exist_ok=True)
        with open(target_path, "w") as f:
            yaml.safe_dump(config.model_dump(), f, default_flow_style=False)
        
        return {"ok": True, "path": str(target_path)}

    def delete_collection_config(self, collection_id: str) -> dict[str, Any]:
        """Delete a collection configuration."""
        if not self.is_enabled():
            return {"ok": False, "error": "Authoring tools are disabled"}
        
        # Validate path
        valid, result = self._validate_path(collection_id)
        if not valid:
            return {"ok": False, "error": result}
        
        target_path = result
        
        if not target_path.exists():
            return {"ok": False, "error": "Collection config not found"}
        
        target_path.unlink()
        return {"ok": True, "deleted": str(target_path)}
