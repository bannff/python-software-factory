"""Authoring tools for notification-module.

Security-sensitive: disabled by default, scoped to config_dir.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from factory.notification.runtime.config import ChannelConfig, TemplateConfig


class AuthoringError(Exception):
    """Error during authoring operations."""
    pass


class AuthoringRuntime:
    """Runtime for config authoring operations.
    
    Security features:
    - Disabled by default (requires NOTIFY_ENABLE_AUTHORING_TOOLS=1)
    - Scoped to config_dir with path traversal protection
    - Validates all configs with Pydantic before writing
    """

    def __init__(self, config_dir: Path | str):
        self.config_dir = Path(config_dir).resolve()

    def is_enabled(self) -> bool:
        """Check if authoring is enabled."""
        return os.environ.get("NOTIFY_ENABLE_AUTHORING_TOOLS") == "1"

    def _check_enabled(self) -> None:
        """Raise if authoring is disabled."""
        if not self.is_enabled():
            raise AuthoringError(
                "Authoring tools are disabled. Set NOTIFY_ENABLE_AUTHORING_TOOLS=1 to enable."
            )

    def _safe_path(self, subdir: str, item_id: str) -> Path:
        """Get safe path within config_dir, blocking traversal."""
        # Block obvious traversal attempts
        if ".." in item_id or item_id.startswith("/"):
            raise AuthoringError(f"Path traversal blocked: {item_id}")
        
        # Sanitize to alphanumeric + dash/underscore
        safe_id = "".join(c for c in item_id if c.isalnum() or c in "-_")
        if not safe_id:
            raise AuthoringError(f"Invalid item ID: {item_id}")
        
        target = (self.config_dir / subdir / f"{safe_id}.yaml").resolve()
        
        # Ensure target is within config_dir
        if not str(target).startswith(str(self.config_dir)):
            raise AuthoringError(f"Path traversal blocked: {item_id}")
        
        return target

    def get_status(self) -> dict[str, Any]:
        """Get authoring status."""
        return {
            "enabled": self.is_enabled(),
            "config_dir": str(self.config_dir),
            "env_var": "NOTIFY_ENABLE_AUTHORING_TOOLS",
        }

    def upsert_channel(self, channel_id: str, data: dict[str, Any]) -> str:
        """Create or update a channel configuration."""
        self._check_enabled()
        
        # Validate with Pydantic
        try:
            data_with_id = {"id": channel_id, **data}
            ChannelConfig.model_validate(data_with_id)
        except ValidationError as e:
            raise AuthoringError(f"Channel validation failed: {e}")
        
        path = self._safe_path("channels", channel_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump(data_with_id, default_flow_style=False))
        
        return str(path)

    def delete_channel(self, channel_id: str) -> bool:
        """Delete a channel configuration."""
        self._check_enabled()
        
        path = self._safe_path("channels", channel_id)
        if path.exists():
            path.unlink()
            return True
        return False

    def upsert_template(self, template_id: str, data: dict[str, Any]) -> str:
        """Create or update a template configuration."""
        self._check_enabled()
        
        # Validate with Pydantic
        try:
            data_with_id = {"id": template_id, **data}
            TemplateConfig.model_validate(data_with_id)
        except ValidationError as e:
            raise AuthoringError(f"Template validation failed: {e}")
        
        path = self._safe_path("templates", template_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump(data_with_id, default_flow_style=False))
        
        return str(path)

    def delete_template(self, template_id: str) -> bool:
        """Delete a template configuration."""
        self._check_enabled()
        
        path = self._safe_path("templates", template_id)
        if path.exists():
            path.unlink()
            return True
        return False
